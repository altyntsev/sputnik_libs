from osgeo import ogr, osr
import re
from alt_proc.dict_ import dict_
import numpy as np
import math
import json

def fast_distance(point0, point1):

    xg0, yg0 = point0
    xg1, yg1 = point1

    k = 111.
    dx = abs((xg1-xg0)) * k * math.cos(math.radians((yg0+yg1)/2))
    dy = abs((yg1-yg0)) * k

    return math.sqrt(dx**2 + dy**2)

def distance(p0, p1, proj=None):

    if proj:
        p = Geom(point=p0, proj=proj)
        p.transform(4326)
        p0 = p.coords()

    # haversine
    R = 6372800  # Earth radius in meters
    xg0, yg0  = p0
    xg1, yg1 = p1

    phi1, phi2 = math.radians(yg0), math.radians(yg1)
    dphi       = math.radians(yg1 - yg0)
    dlambda    = math.radians(xg1 - xg0)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2

    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))

def proj4_from_proj(proj):

    if isinstance(proj, int):
        espg = {
            3857: '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m'
        }
        return espg[proj]
    else:
        return proj

def convert_coords(x, y, from_proj, to_proj):

    geom = Geom(point=(x,y), proj=from_proj)
    geom.to_proj(to_proj)

    return geom.coords()

class Geom():
    
    def __init__(self, gdal_=None, geojson=None, wkt=None, gml=None, polygon=None,
                 check_validity=True, fix_180=True, proj=4326, point=None, points=None):

        self.proj = proj
        if self.proj:
            self.sr = osr.SpatialReference()
            if isinstance(self.proj, (int)):
                self.sr.ImportFromEPSG(self.proj)
            else:
                self.sr.ImportFromProj4(self.proj)

        if polygon is not None:
            ring = ogr.Geometry(ogr.wkbLinearRing)
            if isinstance(polygon, np.ndarray):
                szy, szx = polygon.shape
                if szy==2:
                    for i in range(szx):
                        ring.AddPoint(polygon[0,i].item(), polygon[1,i].item())
            elif isinstance(polygon, list):
                for x, y in polygon:
                    ring.AddPoint(x,y)
            else:
                raise Exception('Unknown polygon data')
            gdal_ = ogr.Geometry(ogr.wkbPolygon)
            gdal_.AddGeometry(ring)

        if point is not None:
            gdal_ = ogr.Geometry(ogr.wkbPoint)
            x, y = point
            gdal_.AddPoint(x, y)
            fix_180 = False

        if points is not None:
            gdal_ = ogr.Geometry(ogr.wkbMultiPoint)
            for x, y in points:
                point = ogr.Geometry(ogr.wkbPoint)
                point.AddPoint(x, y)
                gdal_.AddGeometry(point)
            fix_180 = False

        if geojson:
            if isinstance(geojson, str) and geojson[0]!='{':
                geojson = open(geojson).read()
            if isinstance(geojson, dict):
                geojson = json.dumps(geojson)
            gdal_ = ogr.CreateGeometryFromJson(geojson)
        if wkt:
            gdal_ = ogr.CreateGeometryFromWkt(wkt)
        if gml:
            gdal_ = ogr.CreateGeometryFromGML(str(gml))

        if not gdal_:
            raise Exception('None geometry')
        gdal_.FlattenTo2D()

        if fix_180:
            xg0, xg1, _, _ = gdal_.GetEnvelope()
            if xg0<-90 and xg1>90:
                wkt = 'POLYGON ((0 -90, 0 90, 179.999 90, 179.999 -90, 0 -90))'
                lt180 = ogr.CreateGeometryFromWkt(wkt)
                wkt = 'POLYGON ((180.001 -90, 180.001 90, 360 90, 360 -90, 180.001 -90))'
                gt180 = ogr.CreateGeometryFromWkt(wkt)
                wkt0 = gdal_.ExportToWkt()
                wkt1 = ''
                pos = 0
                for m in re.finditer('[\(,](-\d+)', wkt0):
                    p0, p1 = m.span()
                    xg = float(m.group(1)) + 360
                    wkt1 += wkt0[pos:p0+1] + str(xg)
                    pos = p1
                wkt1 += wkt0[pos:]
                geom1 = ogr.CreateGeometryFromWkt(wkt1)
                geom_gt180 = geom1.Intersection(gt180)
                gdal_ = None
                if not geom_gt180.IsEmpty():
                    gdal_ = geom_gt180
                geom_lt180 = geom1.Intersection(lt180)
                if not geom_lt180.IsEmpty():
                    if gdal_:
                        gdal_ = gdal_.Union(geom_lt180)
                    else:
                        gdal_ = geom_lt180

        if check_validity and not gdal_.IsValid():
            raise Exception('Wrong geometry')

        self.gdal = gdal_

    def to_proj(self, to_proj=None, transform=None):

        if not transform:

            to_sr = osr.SpatialReference()
            to_sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            if isinstance(to_proj, (int)):
                to_sr.ImportFromEPSG(to_proj)
            else:
                to_sr.ImportFromProj4(to_proj)
            transform = osr.CoordinateTransformation(self.sr, to_sr)
        self.gdal.Transform(transform)

    def intersects(self, geom):

        return self.gdal.Intersects(geom.gdal)

    def wkt(self):

        return self.gdal.ExportToWkt()

    def valid(self):

        return self.gdal.IsValid()

    def limits(self):

        x0, x1, y0, y1 = self.gdal.GetEnvelope()

        return dict_(x0=x0, y0=y0, x1=x1, y1=y1)

    def save_as_geojson(self, filename):

        with open(filename, 'w') as f:
            f.write(self.geojson())

    def coverage(self, geom):

        return self.gdal.Intersection(geom.gdal).Area() / self.gdal.Area() * 100

    def coords(self):

        return self.gdal.GetPoint()[:2]

    def area(self):

        return self.gdal.Area()

    def with_in(self, polygon):

        return self.gdal.Within(polygon.gdal)

    def geojson(self):

        return self.gdal.ExportToJson()

    def add(self, geom):

        self.gdal = self.gdal.Union(geom.gdal)
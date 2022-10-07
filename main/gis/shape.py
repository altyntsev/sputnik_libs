import alt.file
import osr, ogr, os
import numpy as np

def write( shpfile, type_, data, proj='longlat', data_proj='longlat'):
    
    driver = ogr.GetDriverByName('ESRI Shapefile')
    if os.path.exists(shpfile):
        alt.file.delete(shpfile)
        alt.file.delete(shpfile.replace('.shp','.shx'))
        alt.file.delete(shpfile.replace('.shp','.proj'))
        alt.file.delete(shpfile.replace('.shp','.dbf'))
    shapeData = driver.CreateDataSource(shpfile)
    
    spatialReference = osr.SpatialReference()
    spatialReference.ImportFromProj4('+proj=%s +datum=WGS84 +no_defs' % proj)
    
    transform = None
    if proj!=data_proj:
        data_spatialReference = osr.SpatialReference()
        data_spatialReference.ImportFromProj4('+proj=%s +datum=WGS84 +no_defs' % data_proj)
        transform = osr.CoordinateTransformation(data_spatialReference, spatialReference)
    
    if type_=='POLY':
        ogr_type = ogr.wkbPolygon
    layer = shapeData.CreateLayer('layer', spatialReference, ogr_type)
    layerDefinition = layer.GetLayerDefn()
    
    item = data[0]
    for key in item:
        if key=='geo':
            continue
        FieldDefinition = ogr.FieldDefn( key, ogr.OFTString )
        FieldDefinition.SetWidth(20)
        layer.CreateField (FieldDefinition)
    
    for i,item in enumerate(data):

        feature = ogr.Feature(layerDefinition)
        feature.SetFID(i)
        for key, value in item.items():
            if key=='geo':
                continue
            feature[key] = value 
        
        geo = item['geo']
        if type_=='POLY':
            if isinstance(geo, np.ndarray):
                ring = ogr.Geometry(ogr.wkbLinearRing)
                if np.any(geo[0,:]!=geo[-1,:]):
                    geo = np.vstack((geo,geo[0,:]))
                N = geo.shape[0]
                for i in range(N):
                    x, y = geo[i]
                    ring.AddPoint(x,y)
                if transform:
                    ring.Transform(transform)    
                    points = ring.GetPoints()
                    ring = ogr.Geometry(ogr.wkbLinearRing)
                    for x, y, z in points:
                        if x<100:
                            x += 360
                        ring.AddPoint(x,y)
                poly = ogr.Geometry(ogr.wkbPolygon)
                poly.AddGeometry(ring)
            if isinstance(geo, ogr.Geometry):
                poly = geo
            feature.SetGeometry(poly)
        layer.CreateFeature(feature)
            
    shapeData.Destroy()
        

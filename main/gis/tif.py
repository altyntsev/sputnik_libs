import gdal, ogr, osr, gdalconst, sys
import os
import re
import numpy as np
import alt_proc.file
import alt_proc.os_
import gis.geom
from alt_proc.dict_ import dict_

def xgyg_to_xy(tif_file, xgyg):

    if not os.path.exists(tif_file):
        raise Exception('File name does not exists : ' + tif_file)
    tif = gdal.Open(tif_file)

    projection = tif.GetProjection()
    xm0, scale, _, ym1, _, _ = tif.GetGeoTransform()

    geom = gis.geom.Geom(points=xgyg)
    geom.to_proj(projection)
    coords = geom.coords()

    coords = [(((xm-xm0)/scale), ((ym1-ym)/scale)) for xm, ym in coords]

    return coords

def meta(tif_file):

    if not os.path.exists(tif_file):
        raise Exception('File name does not exists : ' + tif_file)
    tif = gdal.Open(tif_file)
    band = tif.GetRasterBand(1)

    xm0, scale, _, ym1, _, _ = tif.GetGeoTransform()
    proj = tif.GetProjection()
    epsg = int(re.findall('"EPSG","(\d*)"', proj)[-1])
    meta = dict_(
        szx = tif.RasterXSize,
        szy = tif.RasterYSize,
        n_bands = tif.RasterCount,
        proj = epsg,
        xm0 = xm0,
        xm1 = xm0 + scale * tif.RasterXSize,
        ym0 = ym1 - scale * tif.RasterYSize,
        ym1 = ym1,
        scale = scale,
        nodata = band.GetNoDataValue(),
        dtype = band.ReadAsArray(0,0,1,1).dtype
    )

    return meta

def convert_to_tif(src_file, tif_file=None, nodata=0):

    if tif_file is None:
        tif_file = alt_proc.file.dir(src_file) + alt_proc.file.name(src_file) + '.tif'
    cmd = os.path.dirname(sys.executable) + \
          f'/gdal_translate -of Gtiff -a_nodata {nodata} {src_file} {tif_file}'
    alt_proc.os_.run(cmd)

def write(filename, data, proj4=None, EPSG=None, box=None, palette=None, sample=None,
          compress=False, nodata=None):

    alt_proc.file.delete(filename)
    if isinstance(data, (tuple,list)):
        band_list = True
    else:
        band_list = False
    
    if band_list:
        Nbands = len(data)
        szy, szx = data[0].shape
    else:    
        dim = data.shape
        Ndim = len(dim)
        if Ndim not in [2,3]:
            raise Exception('Wrong data dimension')
        if Ndim==2:
            Nbands = 1
            szy, szx = dim
        else:
            Nbands, szy, szx = dim
            
    if data[0].dtype==np.uint8:
        data_type = gdal.GDT_Byte
    if data[0].dtype==np.uint16:
        data_type = gdal.GDT_UInt16
    if data[0].dtype==np.float32:
        data_type = gdal.GDT_Float32

    gtiff_driver = gdal.GetDriverByName('GTiff')
    options = []
    if compress:
        options.append('COMPRESS=LZW')
    tif = gtiff_driver.Create( filename, szx, szy, Nbands, data_type, options )
    if sample:
        sample_tif = gdal.Open( sample, gdalconst.GA_ReadOnly )
        tif.SetProjection( sample_tif.GetProjection() )
        tif.SetGeoTransform( sample_tif.GetGeoTransform() )
    if box:
        SpatialReference = osr.SpatialReference()
        if proj4:
            SpatialReference.ImportFromProj4(proj4)
        if EPSG:
            SpatialReference.ImportFromEPSG(EPSG)
        tif.SetProjection( SpatialReference.ExportToWkt() )
        tif.SetGeoTransform( (box.x0, (box.x1-box.x0)/szx, 0, box.y1, 0, -(box.y1-box.y0)/szy) ) 
    
    if palette:
        ct = gdal.ColorTable()
        for i,color in palette.items():
            ct.SetColorEntry(i, tuple(color+[255]))
    
    for iband in range(Nbands):
        outBand = tif.GetRasterBand(iband+1)
        if nodata:
            outBand.SetNoDataValue(nodata)
        if palette:
            outBand.SetRasterColorTable( ct )
        if Nbands==1:    
            outBand.WriteArray(data, 0, 0)
        else:
            if band_list:
                outBand.WriteArray(data[iband], 0, 0)
            else:    
                outBand.WriteArray(data[iband,:,:], 0, 0)
        
    del tif

def read(filename):
    
    if not os.path.exists(filename):
        raise Exception('File name does not exists : ' + filename)
    dataset = gdal.Open( filename, gdalconst.GA_ReadOnly )
    bands = []
    for iband in range(dataset.RasterCount):
        band = dataset.GetRasterBand(iband+1)
        data = band.ReadAsArray()
        bands.append(data)

    if len(bands)==1:
        return bands[0]
    else:
        return bands
    
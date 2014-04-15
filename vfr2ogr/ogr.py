import os
import sys
import time

from utils import fatal

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

# check GDAL/OGR library, version >= 1.11 required
def check_ogr():
    # check required version
    version = gdal.__version__.split('.', 1)
    if not (int(version[0]) >= 1 and int(version[1][:2]) >= 11):
        fatal("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
    
    # check if OGR comes with GML driver
    if not ogr.GetDriverByName('GML'):
        fatal('GML driver required')

def open_file(filename):
    drv = ogr.GetDriverByName("GML")
    if drv is None:
        fatal("Unable to select GML driver")
    ds = drv.Open(filename, False)
    if ds is None:
        fatal("Unable to open '%s'" % filename)
        
    return ds

# list formats
def list_formats():
    cnt = ogr.GetDriverCount()
    
    formatsList = [] 
    for i in range(cnt):
        driver = ogr.GetDriver(i)
        if not driver.TestCapability("CreateDataSource"):
            continue
        driverName = driver.GetName()
        if driverName == 'GML':
            continue
        
        formatsList.append(driverName)
    
    for i in sorted(formatsList):
        print i

def get_geom_count(layer):
    defn = layer.GetLayerDefn()
    geom_list = list()
    for i in range(defn.GetGeomFieldCount()):
        geom_list.append([defn.GetGeomFieldDefn(i).GetName(), 0])
    
    for feature in layer:
        for i in range(len(geom_list)):
            if feature.GetGeomFieldRef(i):
                geom_list[i][1] += 1
    
    return geom_list

def list_layers(ds, extended = False):
    nlayers = ds.GetLayerCount()
    layer_list = list()
    for i in range(nlayers):
        layer = ds.GetLayer(i)
        featureCount = layer.GetFeatureCount()
        layerName = layer.GetName()
        layer_list.append(layerName)
        
        if extended:
            print '-' * 80
        print "Number of features in %-20s: %d" % (layerName, featureCount)
        if extended:
            for field, count in get_geom_count(layer):
                print "%41s : %d" % (field, count)
    
    return layer_list

# convert VFR into specified format
def convert_vfr(ids, odsn, frmt, layers=[], overwrite = False, options=[]):
    odrv = ogr.GetDriverByName(frmt)
    if odrv is None:
        fatal("Format '%s' is not supported" % frmt)
    
    # try to open datasource
    ods = odrv.Open(odsn, True)
    if ods is None:
        # if fails, try to create new datasource
        ods = odrv.CreateDataSource(odsn)
    if ods is None:
        fatal("Unable to open/create new datasource '%s'" % odsn)
    
    if overwrite:
        options.append("OVERWRITE=YES")

    start = time.time()
    nlayers = ids.GetLayerCount()
    for i in range(nlayers):
        layer = ids.GetLayer(i)
        layerName = layer.GetName()
        if layers and layerName not in layers:
            continue
        print >> sys.stderr, "Exporing layer %-20s ..." % layerName,
        if not overwrite and ids.GetLayerByName(layerName):
            print >> sys.stderr, " already exists (skipped)"
        else:
            olayer = ods.CopyLayer(layer, layerName, options)
            if olayer is None:
                fatal("Unable to export layer '%s'. Exiting..." % layerName)
            print >> sys.stderr, " %-5d features" % olayer.GetFeatureCount()
    
    end = time.time() - start
    
    ods.Destroy()
    
    return end

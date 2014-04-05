import os
import sys
import time

try:
    from osgeo import gdal, ogr
except:
    sys.exit('ERROR: Import of ogr from osgeo failed')

def fatal(msg):
    sys.exit('ERROR: ' + msg)

def message(msg):
    sys.stderr.write('-' * 80 + os.linesep)
    sys.stderr.write(msg + os.linesep)
    sys.stderr.write('-' * 80 + os.linesep)
    
# check GDAL/OGR library, version >= 1.11 required
def check_ogr():
    # check required version
    version = gdal.__version__.split('.', 1)
    if not (int(version[0]) >= 1 and int(version[1][:2]) >= 11):
        fatal("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
    
    # check if OGR comes with GML driver
    if not ogr.GetDriverByName('GML'):
        fatal('GML driver required')

def check_file(filename):
    if filename.startswith('-'):
        fatal('No input file specified')
    if not os.path.isfile(filename):
        usage()
        fatal("'%s' doesn't exists or is not a file" % filename)
    
    return filename

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

def list_layers(ds):
    nlayers = ds.GetLayerCount()
    for i in range(nlayers):
        layer = ds.GetLayer(i)
        featureCount = layer.GetFeatureCount()
        print "Number of features in %-20s: %d" % (layer.GetName(), featureCount)

# convert VFR into specified format
def convert_vfr(ids, odsn, frmt, overwrite):
    odrv = ogr.GetDriverByName(frmt)
    if odrv is None:
        fatal("Unable to start driver '%s'" % frmt)
    
    # try to open datasource
    ods = odrv.Open(odsn, True)
    if ods is None:
        # if fails, try to create new datasource
        ods = odrv.CreateDataSource(odsn)
    if ods is None:
        fatal("Unable to open/create new datasource '%s'" % odsn)
    
    options = []
    if overwrite:
        options.append("OVERWRITE=YES")

    start = time.time()
    nlayers = ids.GetLayerCount()
    for i in range(nlayers):
        layer = ids.GetLayer(i)
        layerName = layer.GetName()
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

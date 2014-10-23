import os
import sys
import time
import datetime

from utils import fatal, error, message, warning, download_vfr, last_day_of_month, \
    yesterday, remove_option, logger
from vfr import convert_vfr

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

# redirect warnings to the file
def error_handler(err_level, err_no, err_msg):
    if err_level > gdal.CE_Warning:
        raise RuntimeError(err_msg)
    elif err_level == gdal.CE_Debug:
        sys.stderr.write(err_msg + os.linesep)
    else:
        logger.warning(err_msg)

# check GDAL/OGR library, version >= 1.11 required
def check_ogr():
    # check required version
    version = gdal.__version__.split('.', 1)
    if not (int(version[0]) > 1 or int(version[1].split('.', 1)[0]) >= 11):
        fatal("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
    
    # check if OGR comes with GML driver
    if not ogr.GetDriverByName('GML'):
        fatal('GML driver required')

    gdal.PushErrorHandler(error_handler)

# open VFR file for reading
def open_file(filename, download = False, force_date = None):
    drv = ogr.GetDriverByName("GML")
    if drv is None:
        fatal("Unable to select GML driver")
    
    list_ds = list()
    ds = None
    if os.linesep in filename:
        # already list of files (date range)
        return filename.split(os.linesep)
    
    ds = drv.Open(filename, False)
    if ds is None:
        # unable to open input file with GML driver, so it's probably
        # URL list file
        try:
            f = open(filename)
            i = 0
            lines = f.read().splitlines()
            for line in lines:
                if len(line) < 1 or line.startswith('#'):
                    continue # skip empty or commented lines 
                
                if '20' not in line:
                    # determine date if missing
                    if not force_date:
                        if line.startswith('ST_Z'):
                            date = yesterday()
                        else:
                            date = last_day_of_month()
                    else:
                        date = force_date
                    line = date + '_' + line
                
                if not line.endswith('.xml.gz'):
                    # add extension if missing
                    line += '.xml.gz'
                
                if (download or not os.path.exists(line)) and \
                        not line.startswith('http://'):
                    line = 'http://vdp.cuzk.cz/vymenny_format/soucasna/' + line
                
                if download:
                    line = download_vfr(line)
                elif not os.path.exists(line):
                    line = '/vsicurl/' + line
                
                list_ds.append(line)
                i += 1
            message("%d VFR files will be processed..." % len(list_ds))
        except IOError:
            fatal("Unable to read '%s'" % filename)
        f.close()    
    else:
        list_ds.append(filename)
        ds.Destroy()

    return list_ds

# open OGR data-source for reading
def open_ds(filename):
    drv = ogr.GetDriverByName("GML")
    ds = drv.Open(filename, False)
    if ds is None:
        sys.stderr.write("File '%s' not found. Skipping.\n" % filename)
    
    return ds

# list supported OGR formats
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

# get list of geometry column for specified layer
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

# list OGR layers of input VFR file
def list_layers(ds, extended = False, fd = sys.stdout):
    nlayers = ds.GetLayerCount()
    layer_list = list()
    for i in range(nlayers):
        layer = ds.GetLayer(i)
        layerName = layer.GetName()
        layer_list.append(layerName)
        
        if not fd:
            continue

        if extended:
            fd.write('-' * 80 + os.linesep)
        featureCount = layer.GetFeatureCount()
        fd.write("Number of features in %-20s: %d\n" % (layerName, featureCount))
        if extended:
            for field, count in get_geom_count(layer):
                fd.write("%41s : %d\n" % (field, count))
    
    if fd:
        fd.write('-' * 80 + os.linesep)
    
    return layer_list

# print summary for multiple file input
def print_summary(odsn, frmt, layer_list, stime):
    odrv = ogr.GetDriverByName(frmt)
    if odrv is None:
        fatal("Format '%s' is not supported" % frmt)
    
    ods = odrv.Open(odsn, False)
    if ods is None:
        return
    # fatal("Unable to open datasource '%s'" % odsn)

    message("Summary")
    for layer_name in layer_list:
        layer = ods.GetLayerByName(layer_name)
        if not layer:
            continue
        
        sys.stdout.write("Layer            %-20s ... %10d features\n" % (layer_name, layer.GetFeatureCount()))

    nsec = time.time() - stime    
    etime = str(datetime.timedelta(seconds=nsec))
    message("Time elapsed: %s" % str(etime))
    
    ods.Destroy()

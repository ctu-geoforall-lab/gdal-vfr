import os
import sys
import time
import logging

from utils import fatal, message, warning, download_vfr, last_day_of_month

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

logger = logging.getLogger()
logFile = 'log.%d' % os.getpid()
logger.addHandler(logging.FileHandler(logFile, delay = True))

# redirect warnings to the file
def error_handler(err_level, err_no, err_msg):
    if err_level > gdal.CE_Warning:
        raise RuntimeError(err_msg)
    elif err_level == gdal.CE_Debug:
        sys.stderr.write(err_msg + os.linesep)
    else:
        logger.warning(err_msg)

def check_log():
    if os.path.exists(logFile):
        message("WARNINGS LOGGED IN %s" % logFile)

# check GDAL/OGR library, version >= 1.11 required
def check_ogr():
    # check required version
    version = gdal.__version__.split('.', 1)
    if not (int(version[0]) > 1 or int(version[1][:2]) >= 11):
        fatal("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
    
    # check if OGR comes with GML driver
    if not ogr.GetDriverByName('GML'):
        fatal('GML driver required')

    gdal.PushErrorHandler(error_handler)

def open_file(filename, download = False, force_date = None):
    drv = ogr.GetDriverByName("GML")
    if drv is None:
        fatal("Unable to select GML driver")
    
    list_ds = list()
    ds = drv.Open(filename, False)
    if ds is None:
        # unable to open input file with GML driver, so it's probably
        # URL list file
        try:
            f = open(filename)
            i = 0
            lines = f.read().splitlines()
            for line in lines:
                if line.startswith('20'):
                    line = 'http://vdp.cuzk.cz/vymenny_format/soucasna/' + line
                else:
                    if not force_date:
                        date = last_day_of_month()
                    else:
                        date = force_date
                    line = 'http://vdp.cuzk.cz/vymenny_format/soucasna/' + date + '_' + line
                
                if line.startswith('http://'):
                    if download:
                        download_vfr(line)
                        line = os.path.basename(line)
                    else:
                        line = '/vsicurl/' + line
                
                if not line.endswith('.xml.gz'):
                    line += '.xml.gz'
                
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

def open_ds(filename):
    drv = ogr.GetDriverByName("GML")
    ds = drv.Open(filename, False)
    if ds is None:
        warning("Unable to open '%s'. Skipping." % filename)
    
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

def list_layers(ds, extended = False, fd = sys.stdout):
    nlayers = ds.GetLayerCount()
    layer_list = list()
    for i in range(nlayers):
        layer = ds.GetLayer(i)
        featureCount = layer.GetFeatureCount()
        layerName = layer.GetName()
        layer_list.append(layerName)
        
        if not fd:
            continue

        if extended:
            fd.write('-' * 80 + os.linesep)
        fd.write("Number of features in %-20s: %d\n" % (layerName, featureCount))
        if extended:
            for field, count in get_geom_count(layer):
                fd.write("%41s : %d\n" % (field, count))
    
    if fd:
        fd.write('-' * 80 + os.linesep)
    
    return layer_list

# convert VFR into specified format
def convert_vfr(ids, odsn, frmt, layers=[], overwrite = False, options=[], geom_name = None, append = False):
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
    nfeat = 0
    for i in range(nlayers):
        layer = ids.GetLayer(i)
        layerName = layer.GetName()
        
        if layers and layerName not in layers:
            continue
                
        olayer = ods.GetLayerByName('%s' % layerName)
        print >> sys.stdout, "Exporting layer %-20s ..." % layerName,
        if not overwrite and (olayer and not append):
            print >> sys.stdout, " already exists (use --overwrite or --append to modify existing data)"
        else:
            ### TODO: fix output drivers not to use default geometry
            ### names
            if layerName.lower() == 'ulice':
                if 'GEOMETRY_NAME=definicnibod' in options:
                    options.remove('GEOMETRY_NAME=definicnibod')
                options.append('GEOMETRY_NAME=definicnicara')
            else:
                if 'GEOMETRY_NAME=definicnicara' in options:
                    options.remove('GEOMETRY_NAME=definicnicara')
                if 'GEOMETRY_NAME=definicnibod' not in options:
                    options.append('GEOMETRY_NAME=definicnibod')
            
            if not olayer or (not append and olayer and not geom_name):
                olayer = ods.CopyLayer(layer, layerName, options)
                if olayer is None:
                    fatal("Unable to create layer %s" % layerName)
                ifeat = olayer.GetFeatureCount()
            else:
                createFields = False
                if not olayer:
                    if geom_name:
                        geom_type = ogr.wkbMultiPolygon # TODO: remove hardcoded-value
                    else:
                        geom_type = ogr.wkbNone
                    
                    olayer = ods.CreateLayer(layerName,
                                             layer.GetSpatialRef(),
                                             geom_type, options)
                    
                    createFields = True
                
                if not olayer:
                    fatal("Unable to create layer '%'" % layerName)
                
                layer.ResetReading()
                
                feature = layer.GetNextFeature()
                # create attributes
                if createFields:
                    for i in range(feature.GetFieldCount()):
                        olayer.CreateField(feature.GetFieldDefnRef(i))

                olayer.StartTransaction()
                # copy features from source to dest layer
                ifeat = 0
                iFID = olayer.GetFeatureCount()
                while feature:
                    ofeature = feature.Clone()
                    
                    # parse geometry columns if requested
                    if geom_name:
                        odefn = feature.GetDefnRef()
                        idx = feature.GetGeomFieldIndex(geom_name)
                        for i in range(odefn.GetGeomFieldCount()):
                            if i == idx:
                                continue
                            odefn.DeleteGeomFieldDefn(i)
                            geom = feature.GetGeomFieldRef(idx)
                            ofeature.SetGeometry(geom.Clone())

                    ofeature.SetFID(iFID)
                    olayer.CreateFeature(ofeature)
                    
                    feature = layer.GetNextFeature()
                    ifeat += 1
                    iFID += 1

            olayer.CommitTransaction()
            
            if olayer is None:
                fatal("Unable to export layer '%s'. Exiting..." % layerName)
            # ods.SyncToDisk()
            
            print >> sys.stdout, " %-5d features" % ifeat
            nfeat += ifeat
    
    ods.Destroy()
    
    message("Time elapsed: %d sec" % (time.time() - start))
    
    return nfeat

def print_summary(odsn, frmt, layer_list, stime):
    odrv = ogr.GetDriverByName(frmt)
    if odrv is None:
        fatal("Format '%s' is not supported" % frmt)
    
    ods = odrv.Open(odsn, False)
    if ods is None:
        fatal("Unable to open datasource '%s'" % odsn)

    message("Summary")
    for layerName in layer_list:
        layer = ods.GetLayerByName(layerName)
        if not layer:
            continue
        
        print >> sys.stderr, "Layer          %-20s ... %-5d features" % (layerName, layer.GetFeatureCount())
    
    message("Time elapsed: %d sec" % (time.time() - stime))
    
    ods.Destroy()

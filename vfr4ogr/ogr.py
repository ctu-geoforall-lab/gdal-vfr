import os
import sys
import time
import logging

from utils import fatal, message, warning, download_vfr, last_day_of_month, remove_option

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
    
    create_geom = ods.TestCapability(ogr.ODsCCreateGeomFieldAfterCreateLayer)
    if not create_geom:
        warning("Driver '%s' doesn't support multiple geometry columns. "
                "Only first will be used." % odrv.GetName())
    
    if overwrite:
        options.append("OVERWRITE=YES")

    start = time.time()
    nlayers = ids.GetLayerCount()
    nfeat = 0
    for iLayer in range(nlayers):
        layer = ids.GetLayer(iLayer)
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
            if frmt in ('PostgreSQL', 'OCI') and not geom_name:
                if layerName.lower() == 'ulice':
                    remove_option(options, 'GEOMETRY_NAME')
                    options.append('GEOMETRY_NAME=definicnicara')
                else:
                    remove_option(options, 'GEOMETRY_NAME')
                    options.append('GEOMETRY_NAME=definicnibod')
            
            # delete layer if exists and append is not True
            if olayer and not append:
                nlayersOut = ods.GetLayerCount()
                for iLayerOut in range(nlayersOut): # do it better
                    if ids.GetLayer(iLayerOut).GetName() == layerName:
                        ods.DeleteLayer(iLayerOut)
                        olayer = None
                        break
            
            # if not olayer or (not append and olayer and not geom_name):
            if False: # disabled (do not preserve fid...)
                olayer = ods.CopyLayer(layer, layerName, options)
                if olayer is None:
                    fatal("Unable to create layer %s" % layerName)
                ifeat = olayer.GetFeatureCount()
            else:
                createFields = False
                if not olayer:

                    # determine geometry type
                    if geom_name or not create_geom:
                        feat_defn = layer.GetLayerDefn()
                        if geom_name:
                            idx = feat_defn.GetGeomFieldIndex(geom_name)
                        else:
                            idx = 0
                        
                        if idx > -1:
                            geom_type = feat_defn.GetGeomFieldDefn(idx).GetType()
                        else:
                            # warning("Layer '%s': geometry '%s' not available" % (layerName, geom_name))
                            geom_type = layer.GetGeomType()
                            idx = 0

                        if frmt in ('PostgreSQL', 'OCI'):
                            remove_option(options, 'GEOMETRY_NAME')
                            options.append('GEOMETRY_NAME=%s' % feat_defn.GetGeomFieldDefn(idx).GetName().lower())
                    else:
                        geom_type = ogr.wkbNone
                    
                    # create new layer
                    olayer = ods.CreateLayer(layerName,
                                             layer.GetSpatialRef(),
                                             geom_type, options)
                    
                    createFields = True
                
                if not olayer:
                    fatal("Unable to create layer '%'" % layerName)
                                
                # create attributes
                if createFields:
                    feat_defn = layer.GetLayerDefn()
                    for i in range(feat_defn.GetFieldCount()):
                        olayer.CreateField(feat_defn.GetFieldDefn(i))
                    # create also geometry attributes
                    if not geom_name and \
                            olayer.TestCapability(ogr.OLCCreateGeomField):
                        for i in range(feat_defn.GetGeomFieldCount()):
                            geom_defn = feat_defn.GetGeomFieldDefn(i) 
                            if geom_name and geom_defn.GetName() != geom_name:
                                continue
                            olayer.CreateGeomField(feat_defn.GetGeomFieldDefn(i))
                
                if olayer.TestCapability(ogr.OLCTransactions):
                    olayer.StartTransaction()
                
                # copy features from source to dest layer
                ifeat = 0
                iFID = olayer.GetFeatureCount() + 1
                geom_idx = -1

                layer.ResetReading()
                feature = layer.GetNextFeature()
                while feature:
                    ofeature = feature.Clone()
                    
                    # parse geometry columns if requested
                    if geom_name:
                        if geom_idx < 0:
                            odefn = feature.GetDefnRef()
                            geom_idx = feature.GetGeomFieldIndex(geom_name)
                        
                        # set requested geometry
                        if geom_idx > -1:
                            geom = feature.GetGeomFieldRef(geom_idx)
                            if geom:
                                ofeature.SetGeometry(geom.Clone())
                        
                        # delete remaining geometry columns
                        for i in range(odefn.GetGeomFieldCount()):
                            if i == geom_idx:
                                continue
                            odefn.DeleteGeomFieldDefn(i)
                    
                    ofeature.SetFID(iFID)
                    olayer.CreateFeature(ofeature)
                    
                    feature = layer.GetNextFeature()
                    ifeat += 1
                    iFID += 1

                if olayer.TestCapability(ogr.OLCTransactions):
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

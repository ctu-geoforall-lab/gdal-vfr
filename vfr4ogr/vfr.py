import time
import sys

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from utils import message, remove_option
from vfr_changes import delete_features, process_changes

# modify output feature - remove remaining geometry columns
def modify_ofeature(feature, geom_idx, ofeature):
    # set requested geometry
    if geom_idx > -1:
        geom = feature.GetGeomFieldRef(geom_idx)
        if geom:
            ofeature.SetGeometry(geom.Clone())
                        
    # delete remaining geometry columns
    odefn = feature.GetDefnRef()
    for i in range(odefn.GetGeomFieldCount()):
        if i == geom_idx:
            continue
        odefn.DeleteGeomFieldDefn(i)

    return geom_idx

# write VFR features to output data-source
def convert_vfr(ids, odsn, frmt, layers=[], overwrite = False, options=[], geom_name = None,
                mode = Mode.write):
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
    if not geom_name and not create_geom:
        warning("Driver '%s' doesn't support multiple geometry columns. "
                "Only first will be used." % odrv.GetName())
    
    if overwrite:
        options.append("OVERWRITE=YES")

    # process deleted features first
    dlist = None
    if mode == Mode.change:
        dlayer = ods.GetLayerByName('ZaniklePrvky')
        if dlayer:
            dlist = delete_features(dlayer, ods)
    
    start = time.time()
    nlayers = ids.GetLayerCount()
    nfeat = 0
    for iLayer in range(nlayers):
        layer = ids.GetLayer(iLayer)
        layer_name = layer.GetName()
        
        if layers and layer_name not in layers:
            # process only selected layers
            continue
                
        if layer_name == 'ZaniklePrvky':
            # process deleted features
            continue
        
        olayer = ods.GetLayerByName('%s' % layer_name)
        sys.stdout.write("Processing layer %-20s ..." % layer_name)
        if not overwrite and (olayer and mode == Mode.write):
            sys.stdout.write(" already exists (use --overwrite or --append to modify existing data)\n")
            continue

        ### TODO: fix output drivers not to use default geometry
        ### names
        if frmt in ('PostgreSQL', 'OCI') and not geom_name:
            if layer_name.lower() == 'ulice':
                remove_option(options, 'GEOMETRY_NAME')
                options.append('GEOMETRY_NAME=definicnicara')
            else:
                remove_option(options, 'GEOMETRY_NAME')
                options.append('GEOMETRY_NAME=definicnibod')
            
        # delete layer if exists and append is not True
        if olayer and mode == Mode.write:
            if delete_layer(ids, ods, layer_name):
                olayer = None
            
        # if not olayer or (not append and olayer and not geom_name):
        ### olayer = ods.CopyLayer(layer, layer_name, options)
        ### if olayer is None:
        ### fatal("Unable to create layer %s" % layer_name)
        ### ifeat = olayer.GetFeatureCount()

        # create new layer if not exists
        if not olayer:
            olayer = create_layer(ods, layer,
                                  layer_name, geom_name, create_geom, options)

        if olayer is None:
            fatal("Unable to export layer '%s'. Exiting..." % layer_name)
        
        # pre-process changes
        if mode == Mode.change:
            change_list = process_changes(layer, olayer)
        
        ifeat = 0
        fid_before = fid = olayer.GetFeatureCount()
        geom_idx = -1

        # start transaction in output layer
        if olayer.TestCapability(ogr.OLCTransactions):
            olayer.StartTransaction()
        
        # copy features from source to destination layer
        layer.ResetReading()
        feature = layer.GetNextFeature()
        while feature:
            # check for changes first
            if mode == Mode.change:
                c_fid = feature.GetFID()
                action = change_list.get(c_fid, None)
                
                # feature marked to be changed (delete first)
                if action in (Action.delete, Action.update):
                    olayer.DeleteFeature(c_fid)
                
                if action == Action.add:
                    fid_before += 1
                    fid = fid_before
                else:
                    fid = c_fid
                
                if action == Action.delete:
                    # do nothing else and continue
                    continue 
            else:
                fid += 1
            
            # clone feature
            ofeature = feature.Clone()
        
            # modify geometry columns if requested
            if mode == Mode.write and geom_name:
                if geom_idx < 0:
                    geom_idx = feature.GetGeomFieldIndex(geom_name)
                modify_feature(feature, geom_idx, ofeature)
            
            # set feature id
            ofeature.SetFID(fid)
            # add new feature to output layer
            olayer.CreateFeature(ofeature)
                    
            feature = layer.GetNextFeature()
            ifeat += 1
        
        # commit transaction in output layer
        if olayer.TestCapability(ogr.OLCTransactions):
            olayer.CommitTransaction()
            
        sys.stdout.write(" %10d features" % ifeat)
        if mode == Mode.change:
            n_added = n_updated = n_deleted = 0
            for action in change_list.itervalues():
                if action == Action.update:
                    n_updated += 1
                else: # Action.add
                    n_added += 1
                n_deleted = dlist.get(layer_name, 0)
            sys.stdout.write(" (%5d added, %5d updated, %5d deleted)" % \
                                 (n_added, n_updated, n_deleted))
        sys.stdout.write("\n")
        
        nfeat += ifeat
    
    ### ods.SyncToDisk()
    ods.Destroy()
    
    message("Time elapsed: %d sec" % (time.time() - start))
    
    return nfeat

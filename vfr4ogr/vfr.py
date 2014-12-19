import time
import sys

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from utils import message, remove_option, Mode, Action, warning, fatal
from vfr_changes import process_changes, process_deleted_features
from pgutils import update_fid_seq, get_fid_max

# modify output feature - remove remaining geometry columns
def modify_feature(feature, geom_idx, ofeature, suppress=False):
    # set requested geometry
    if geom_idx > -1:
        geom = feature.GetGeomFieldRef(geom_idx)
        if geom:
            ofeature.SetGeometry(geom.Clone())
        else:
            ofeature.SetGeometry(None)
            if not suppress:
                warning("Feature %d has no geometry (geometry column: %d)" % \
                            (feature.GetFID(), geom_idx))
    
    return geom_idx


# delete specified layer from output data-source
def delete_layer(ids, ods, layerName):
    nlayersOut = ods.GetLayerCount()
    for iLayerOut in range(nlayersOut): # do it better
        if ods.GetLayer(iLayerOut).GetName() == layerName:
            ods.DeleteLayer(iLayerOut)
            return True
    
    return False

# create new layer in output data-source
def create_layer(ods, ilayer, layerName, geom_name, create_geom, options):
    ofrmt = ods.GetDriver().GetName()
    # determine geometry type
    if geom_name or not create_geom:
        feat_defn = ilayer.GetLayerDefn()
        if geom_name:
            idx = feat_defn.GetGeomFieldIndex(geom_name)
        else:
            idx = 0
            
        if idx > -1:
            geom_type = feat_defn.GetGeomFieldDefn(idx).GetType()
        else:
            # warning("Layer '%s': geometry '%s' not available" % (layerName, geom_name))
            geom_type = ilayer.GetGeomType()
            idx = 0

        if ofrmt in ('PostgreSQL', 'OCI'):
            remove_option(options, 'GEOMETRY_NAME')
            options.append('GEOMETRY_NAME=%s' % feat_defn.GetGeomFieldDefn(idx).GetName().lower())
    else:
        geom_type = ogr.wkbNone
    
    # create new layer
    olayer = ods.CreateLayer(layerName, ilayer.GetSpatialRef(),
                             geom_type, options)
    
    if not olayer:
        fatal("Unable to create layer '%'" % layerName)
           
    # create attributes                     
    feat_defn = ilayer.GetLayerDefn()
    for i in range(feat_defn.GetFieldCount()):
        ifield = feat_defn.GetFieldDefn(i)
        ofield = ogr.FieldDefn(ifield.GetNameRef(), ifield.GetType())
        ofield.SetWidth(ifield.GetWidth())
        if ofrmt == 'ESRI Shapefile':
            # StringList not supported by Esri Shapefile
            if ifield.GetType() in (ogr.OFTIntegerList, ogr.OFTRealList, ogr.OFTStringList):
                ofield.SetType(ogr.OFTString)
        
        olayer.CreateField(ofield)

    # create also geometry attributes
    if not geom_name and \
            olayer.TestCapability(ogr.OLCCreateGeomField):
        for i in range(feat_defn.GetGeomFieldCount()):
            geom_defn = feat_defn.GetGeomFieldDefn(i) 
            if geom_name and geom_defn.GetName() != geom_name:
                continue
            olayer.CreateGeomField(feat_defn.GetGeomFieldDefn(i))
    
    return olayer

# write VFR features to output data-source
def convert_vfr(ids, odsn, frmt, layers=[], overwrite = False, options=[], geom_name = None,
                mode = Mode.write, nogeomskip = True, userdata={}):
    odrv = ogr.GetDriverByName(frmt)
    if odrv is None:
        fatal("Format '%s' is not supported" % frmt)
    
    # try to open datasource
    ods = odrv.Open(odsn, True)
    if ods is None:
        # if fails, try to create new datasource
        ods = odrv.CreateDataSource(odsn)
    if ods is None:
        fatal("Unable to open or create new datasource '%s'" % odsn)
    
    create_geom = ods.TestCapability(ogr.ODsCCreateGeomFieldAfterCreateLayer)
    if not geom_name and not create_geom:
        warning("Driver '%s' doesn't support multiple geometry columns. "
                "Only first will be used." % odrv.GetName())
    
    # OVERWRITE is not support by Esri Shapefile
    if overwrite:
        if frmt != 'ESRI Shapefile':
            options.append("OVERWRITE=YES")
        if mode == Mode.write:
            # delete also layers which are not part of ST_UKSH
            for layer in ("ulice", "parcely", "stavebniobjekty", "adresnimista"):
                if ods.GetLayerByName(layer) is not None:
                    ods.DeleteLayer(layer)
    
    # process features marked for deletion first
    dlist = None # statistics
    if mode == Mode.change:
        dlayer = ids.GetLayerByName('ZaniklePrvky')
        if dlayer:
            dlist = process_deleted_features(dlayer, ods, layers)
    
    # process layers
    start = time.time()
    nlayers = ids.GetLayerCount()
    nfeat = 0
    for iLayer in range(nlayers):
        layer = ids.GetLayer(iLayer)
        layer_name = layer.GetName()
        ### force lower case for output layers, some drivers are doing
        ### that automatically anyway
        layer_name_lower = layer_name.lower()

        if layers and layer_name not in layers:
            # process only selected layers
            continue
        
        if layer_name == 'ZaniklePrvky':
            # skip deleted features (already done)
            continue
        
        olayer = ods.GetLayerByName('%s' % layer_name_lower)
        sys.stdout.write("Processing layer %-20s ..." % layer_name)
        if not overwrite and (olayer and mode == Mode.write):
            sys.stdout.write(" already exists (use --overwrite or --append to modify existing data)\n")
            continue

        ### TODO: fix output drivers not to use default geometry
        ### names
        if frmt in ('PostgreSQL', 'OCI') and not geom_name:
            if layer_name_lower == 'ulice':
                remove_option(options, 'GEOMETRY_NAME')
                options.append('GEOMETRY_NAME=definicnicara')
            else:
                remove_option(options, 'GEOMETRY_NAME')
                options.append('GEOMETRY_NAME=definicnibod')
        
        # delete layer if exists and append is not True
        if olayer and mode == Mode.write:
            if delete_layer(ids, ods, layer_name_lower):
                olayer = None
        
        # create new output layer if not exists
        if not olayer:
            olayer = create_layer(ods, layer,
                                  layer_name_lower, geom_name, create_geom, options)
        if olayer is None:
            fatal("Unable to export layer '%s'. Exiting..." % layer_name)
        
        # pre-process changes
        if mode == Mode.change:
            change_list = process_changes(layer, olayer)
            if dlist and layer_name in dlist: # add features to be deleted
                change_list.update(dlist[layer_name])

        ifeat = n_nogeom = 0
        geom_idx = -1
        
        # make sure that PG sequence is up-to-date (import for fid == -1)
	fid = -1
        if 'pgconn' in userdata:
            fid = get_fid_max(userdata['pgconn'], layer_name_lower)
            if fid > 0:
                update_fid_seq(userdata['pgconn'], layer_name_lower, fid)
        if fid is None or fid == -1:
            fid = olayer.GetFeatureCount()
        
        # start transaction in output layer
        if olayer.TestCapability(ogr.OLCTransactions):
            olayer.StartTransaction()

        # delete marked features first (changes only)
        if mode == Mode.change and dlist and layer_name in dlist:
            for fid in dlist[layer_name].keys():
                olayer.DeleteFeature(fid)

        # do mapping for fields (needed for Esri Shapefile when
        # field names are truncated)
        field_map = [i for i in range(0, layer.GetLayerDefn().GetFieldCount())]
        
        # copy features from source to destination layer
        layer.ResetReading()
        feature = layer.GetNextFeature()
        while feature:
            # check for changes first (delete/update/add)
            if mode == Mode.change:
                c_fid = feature.GetFID()
                action, o_fid = change_list.get(c_fid, (None, None))
                if action is None:
                    fatal("Layer %s: unable to find feature %d" % (layer_name, c_fid))
                
                # feature marked to be changed (delete first)
                if action in (Action.delete, Action.update):
                    olayer.DeleteFeature(o_fid)
                
                # determine fid for new feature
                if action == Action.add:
                    fid = -1
                else:
                    fid = o_fid
                
                if action == Action.delete:
                    # do nothing and continue
                    feature = layer.GetNextFeature()
                    ifeat += 1
                    continue
            else:
                fid += 1
            
            # clone feature
            ### ofeature = feature.Clone() # replace by SetFrom()
            ofeature = ogr.Feature(olayer.GetLayerDefn())
            ofeature.SetFromWithMap(feature, True, field_map)
            
            # modify geometry columns if requested
            if geom_name:
                if geom_idx < 0:
                    geom_idx = feature.GetGeomFieldIndex(geom_name)
                    
                    # delete remaining geometry columns
                    ### not needed - see SetFrom()
                    ### odefn = ofeature.GetDefnRef()
                    ### for i in range(odefn.GetGeomFieldCount()):
                    ###    if i == geom_idx:
                    ###        continue
                    ###    odefn.DeleteGeomFieldDefn(i)
                
                modify_feature(feature, geom_idx, ofeature)
            
            if ofeature.GetGeometryRef() is None:
                n_nogeom += 1
                if nogeomskip:
                    # skip feature without geometry
                    feature = layer.GetNextFeature()
                    ofeature.Destroy()
                    continue

            # set feature id
            if fid >= -1:
                # fid == -1 -> unknown fid
                ofeature.SetFID(fid)
                
            # add new feature to output layer
            olayer.CreateFeature(ofeature)
            
            feature = layer.GetNextFeature()
            ifeat += 1
        
        # commit transaction in output layer
        if olayer.TestCapability(ogr.OLCTransactions):
            olayer.CommitTransaction()
            
        # print statistics per layer
        sys.stdout.write(" %10d features" % ifeat)
        if mode == Mode.change:
            n_added = n_updated = n_deleted = 0
            for action, unused in change_list.itervalues():
                if action == Action.update:
                    n_updated += 1
                elif action == Action.add:
                    n_added += 1
                else: # Action.delete:
                    n_deleted += 1
            sys.stdout.write(" (%5d added, %5d updated, %5d deleted)" % \
                                 (n_added, n_updated, n_deleted))
        else:
            sys.stdout.write(" added")
            if n_nogeom > 0:
                if nogeomskip:
                    sys.stdout.write(" (%d without geometry skipped)" % n_nogeom)
                else:
                    sys.stdout.write(" (%d without geometry)" % n_nogeom)
        sys.stdout.write("\n")
        
        nfeat += ifeat

        # update sequence for PG
        if 'pgconn' in userdata:
            ### fid = get_fid_max(userdata['pgconn'], layer_name_lower)
            if fid > 0:
                update_fid_seq(userdata['pgconn'], layer_name_lower, fid)
                
    # close output datasource
    ods.Destroy()

    # final statistics (time elapsed)
    message("Time elapsed: %d sec" % (time.time() - start))
    
    return nfeat

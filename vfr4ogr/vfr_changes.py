from utils import Action, warning, error

# process list of features (per layer) to be modified (update/add)
#
# returns directory where keys are fids from input (VFR) layer and
# items are tuples (action, fid of existing feature if found)
#
# TODO: use numeric data as key
def process_changes(ilayer, olayer, column='gml_id'):
    changes_list = {}
    
    ilayer.ResetReading()
    ifeature = ilayer.GetNextFeature()
    while ifeature:
        fcode = ifeature.GetField(column)
        # check if feature already exists in output layer
        found = []
        olayer.SetAttributeFilter("%s = '%s'" % (column, fcode))
        for feature in olayer:
            found.append(feature.GetFID())
        
        n_feat = len(found)
        if n_feat > 1:
            # TODO: how to handle correctly?
            warning("Layer '%s': %d features '%s=%s' found, skipping..." % \
                        (olayer.GetName(), n_feat, column, fcode))
        else:
            changes_list[ifeature.GetFID()] = (Action.update, found[0]) if n_feat > 0 else (Action.add, -1)
        
        ifeature = ilayer.GetNextFeature()
    
    # unset attribute filter
    olayer.SetAttributeFilter(None)
    
    return changes_list

# process deleted features (process OGR layer 'ZaniklePrvky')
def process_deleted_features(layer, ods):
    lcode2lname = {
        'ST' : 'Staty',
        'RS' : 'RegionySoudrznosti',
        'KR' : 'Kraje',
        'VC' : 'Vusc',
        'OK' : 'Okresy',
        'OP' : 'Orp',
        'PU' : 'Pou',
        'OB' : 'Obce',
        'SP' : 'SpravniObvody',
        'MP' : 'Mop',
        'MC' : 'Momc',
        'CO' : 'CastiObci',
        'KU' : 'KatastralniUzemi',
        'ZJ' : 'Zsj',
        'UL' : 'Ulice',
        'PA' : 'Parcely',
        'SO' : 'StavebniObjekty',
        'AD' : 'AdresniMista',
        }
    column = 'gml_id'
    dlist = {}
    for layer_name in lcode2lname.itervalues():
        dlist[layer_name] = {}
    
    layer.ResetReading()
    feature = layer.GetNextFeature()
    layer_previous = None
    while feature:
        # determine layer and attribute filter for given feature
        lcode = feature.GetField("TypPrvkuKod")
        layer_name = lcode2lname.get(lcode, None)
        if not layer_name:
            error("Unknown layer code '%s'" % lcode)
            continue
        fcode = "%s.%s" % (lcode, feature.GetField("PrvekId"))
        if not layer_previous or layer_previous != layer_name:
            dlayer = ods.GetLayerByName('%s' % layer_name)
            if dlayer is None:
                error("Layer '%s' not found" % layer_name)
                continue
        
        # find features to be deleted (collect their FIDs)
        n_feat = 0
        dlayer.SetAttributeFilter("%s = '%s'" % (column, fcode))
        for dfeature in dlayer:
            fid = dfeature.GetFID()
            dlist[layer_name][fid] = (Action.delete, fid)
            n_feat += 1
        dlayer.SetAttributeFilter(None)
        
        # check for consistency (one feature should be found)
        if n_feat == 0:
            warning("No feature in layer '%s' ('%s') found. Nothing to delete." % \
                        (layer_name, fcode))
        elif n_feat > 1:
            warning("More feature in layer '%s' with '%s' found" % (layer_name, fcode))
        
        layer_previous = layer_name
        feature = layer.GetNextFeature()
    
    # return statistics
    return dlist

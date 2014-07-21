# check changes
# TODO: process deleted features
# TODO: use numeric data as key
def process_changes(ilayer, olayer, column='gml_id'):
    changes_list = {}
    
    ilayer.ResetReading()
    ifeature = ilayer.GetNextFeature()
    while ifeature:
        fcode = ifeature.GetField(column)
        olayer.SetAttributeFilter("%s = '%s'" % (column, fcode))
        
        found = []
        for feature in olayer:
            found.append(feature)
        
        n_feat = len(found)
        if n_feat > 1:
            warning("Layer '%s': %d features '%s=%s' found, skipping..." % \
                        (olayer.GetName(), len(found), column, fcode))
        else:
            changes_list[ifeature.GetFID()] = Action.update if n_feat > 0 else Action.add
        
        ifeature = ilayer.GetNextFeature()
    
    # unset attribute filter
    olayer.SetAttributeFilter(None)
    
    return changes_list

# delete features
def delete_features(layer, ods):
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
        dlist[layer_name.lower()] = 0
    
    layer.ResetReading()
    feature = layer.GetNextFeature()
    layer_previous = None
    while feature:
        # determine layer
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
        
        # find features to be deleted
        dlayer.SetAttributeFilter("%s = '%s'" % (column, fcode))
        dfeature_list = []
        for dfeature in dlayer:
            dfeature_list.append(dfeature.GetFID())
            dlist[layer_name.lower()] += 1
        
        if len(dfeature_list) == 0:
            warning("No feature in layer '%s' ('%s') found. Nothing to delete." % \
                        (layer_name, fcode))
        elif len(dfeature_list) > 1:
            warning("More feature in layer '%s' with '%s' found" % (layer_name, fcode))
        dlayer.SetAttributeFilter(None)

        # delete features
        for dfeature in dfeature_list:
            dlayer.DeleteFeature(dfeature)
        
        layer_previous = layer_name
        feature = layer.GetNextFeature()

    # return statistics
    print dlist
    return dlist

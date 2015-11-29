#!/usr/bin/env python

###############################################################################
#
# VFR importer based on GDAL library
#
# Author: Martin Landa <landa.martin gmail.com>
#
# Licence: MIT/X
#
###############################################################################

"""
Exports VFR data from PostGIS database to various formats.

Requires GDAL library version 1.11 or later.

Usage: vfr2py [-f]  --dbname <database name>
                    [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]
                    [--format=<output format>] [--dsn=<OGR datasource>]
                    [--overwrite]

       -f          List supported output formats
       -g          Skip features without geometry
       --dbname    Input PostGIS database
       --schema    Schema name (default: public)
       --user      User name
       --passwd    Password
       --host      Host name
       --layer     Export only selected layers separated by comma (if not given all layers are processed)
       --format    Output format
       --dsn       Output OGR datasource
       --overwrite Overwrite existing output data
"""

import sys
import atexit
from getopt import GetoptError

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from vfr4ogr.ogr import check_ogr, list_layers
from vfr4ogr.vfr import create_layer, modify_feature
from vfr4ogr.utils import fatal, check_log
from vfr4ogr.parse import get_opt
from vfr4ogr.pgutils import build_dsn

# print program usage
def usage():
    print __doc__

def export_layers(ids, ods, layers, overwrite, nogeomskip, active_schema):
    """Export PostGIS layers into given output format

    @param ids: input OGR datasource
    @param ods: output OGR datasource
    @param overwrite: True to overwrite output datasource
    @param nogeomskip: True to not skip features without geometry
    @param active schema: name of schema with tables to be exported
    """
    nlayers = ids.GetLayerCount()
    for i in range(nlayers):
        layer = ids.GetLayer(i)
        layerName = layer.GetName()
        if layers and layerName not in layers:
            continue
        
        if active_schema: # do it better
            try:
                schema, table = layerName.split('.', 1)
            except:
                schema = None
            if schema and schema != active_schema:
                continue # skip table from non-active schema
        
        defn = layer.GetLayerDefn()
        for i in range(defn.GetGeomFieldCount()):
            geom = defn.GetGeomFieldDefn(i).GetName()
            olayerName = '%s_%s' % (layerName, geom)
            sys.stdout.write("Exporting %-45s..." % olayerName)

            olayer = ods.GetLayerByName('%s' % olayerName)
            if not overwrite and olayer:
                sys.stdout.write(" already exists (use --overwrite or --append to modify existing data)\n")
                continue

            # delete layer if exists
            if olayer:
                nlayersOut = ods.GetLayerCount()
                for iLayerOut in range(nlayersOut): # do it better
                    if ods.GetLayer(iLayerOut).GetName() == olayerName:
                        ods.DeleteLayer(iLayerOut)
                        break
                olayer = None

            # create new output layer if not exists
            if not olayer:
                olayer = create_layer(ods, layer,
                                      olayerName, geom, False, [])
                if olayer is None:
                    fatal("Unable to export layer '%s'. Exiting..." % olayerName)

            # start transaction in output layer
            if olayer.TestCapability(ogr.OLCTransactions):
                olayer.StartTransaction()
            
            # do mapping for fields (needed for Esri Shapefile when
            # field names are truncated)
            field_map = [i for i in range(0, layer.GetLayerDefn().GetFieldCount())]
            
            # copy features from source to destination layer
            geom_idx = -1
            fid = n_nogeom = 0
            feat_without_geom = []
            
            layer.ResetReading()
            feature = layer.GetNextFeature()
            while feature:
                ofeature = ogr.Feature(olayer.GetLayerDefn())
                ofeature.SetFromWithMap(feature, True, field_map)
                if geom_idx < 0:
                    geom_idx = feature.GetGeomFieldIndex(geom)
                modify_feature(feature, geom_idx, ofeature, True)
                
                # add new feature to output layer
                fid += 1
                ofeature.SetFID(fid)
                olayer.CreateFeature(ofeature)
                
                if ofeature.GetGeometryRef() is None:
                    # feature without geometry
                    feat_without_geom.append(fid)
                
                feature = layer.GetNextFeature()

            # collect statistics about features without geometry
            n_feat_no_geom = len(feat_without_geom)
            if n_feat_no_geom > 0 and \
               n_feat_no_geom != layer.GetFeatureCount():
                if not nogeomskip:
                    feat_without_geom = [] 
            
            # print statistics per layer
            sys.stdout.write(" %10d features exported" % fid)

            # delete features without geometry if requested
            if len(feat_without_geom) > 0:
                for fid in feat_without_geom:
                    olayer.DeleteFeature(fid)
                sys.stdout.write(" (%d without geometry skipped)" % n_feat_no_geom)
            
            # commit transaction in output layer
            if olayer.TestCapability(ogr.OLCTransactions):
                olayer.CommitTransaction()
            
            sys.stdout.write("\n")
            
def main():
    # check requirements
    check_ogr()
    
    # parse cmdline arguments
    options = { 'dbname' : None, 'schema' : None, 'user' : None, 'passwd' : None, 'host' : None, 
                'overwrite' : False, 'layer' : [], 'format' : None, 'dsn' : None, 'nogeomskip': False }
                
    try:
        get_opt(sys.argv, "ofg", ["help", "overwrite",
                                  "dbname=", "schema=", "user=", "passwd=", "host=", "layer=",
                                  "format=", "dsn="], options)
    except GetoptError, e:
        usage()
        if str(e):
            fatal(e)
        else:
            sys.exit(0)

    # build datasource name
    idsn = build_dsn(options)
    if not idsn:
        usage()
        fatal("--dbname required")
    if options['schema']:
        idsn += " active_schema=%s" % options['schema']
    
    # open input PostGIS database
    idrv = ogr.GetDriverByName('PostgreSQL')
    if idrv is None:
        fatal("Format '%s' is not supported" % 'PostgreSQL')
    ids = idrv.Open(idsn, False)
    if ids is None:
        fatal("Unable to connect to input DB")

    # get list of layers
    layer_list = options['layer']
    if layer_list:
        layer_list_all = layer_list
    else:
        layer_list_all = []

    if options.get('dsn', None) is None:
        # no output datasource given -> list available layers and exit
        list_layers(ids, False, sys.stdout)
        return 0

    if options.get('format', None) is None:
        fatal("--format required")
    
    # open/create output datasource
    odrv = ogr.GetDriverByName(options['format'])
    if odrv is None:
        fatal("Format '%s' is not supported" % options['format'])
    ods = odrv.Open(options['dsn'], True)
    if ods is None:
        # if fails, try to create new datasource
        ods = odrv.CreateDataSource(options['dsn'])
    if ods is None:
        fatal("Unable to open/create new datasource '%s'" % options['dsn'])

    # export selected layers to destination datasource
    export_layers(ids, ods, layer_list_all, options['overwrite'], options['nogeomskip'], options['schema'])

    # close input and output datasources
    ids.Destroy()
    ods.Destroy()
    
    # delete layers with 0 features
    ods = odrv.Open(options['dsn'], True)
    deleted = True
    while deleted:
        nCount = ods.GetLayerCount()
        deleted = False
        for iLayerOut in range(nCount): # do it better
            if ods.GetLayer(iLayerOut).GetFeatureCount() < 1:
                ods.DeleteLayer(iLayerOut)
                deleted = True
                break
            
    ods.Destroy()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

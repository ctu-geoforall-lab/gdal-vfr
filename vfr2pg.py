#!/usr/bin/env python

"""
Imports VFR data to PostGIS database

Requires GDAL/OGR library version 1.11 or later.

One of input options must be given:
       --file
       --type

Usage: vfr2py [-e] [-d] [-s] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_XXXXXX_ABCD] [--layer=layer1,layer2,...] [--geom=OriginalniHranice|GeneralizovaneHranice]
                              --dbname <database name>
                             [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]
                             [--overwrite] [--append]

       -e          Extended layer list statistics
       -d          Save downloaded VFR data in currect directory (--type required)
       -s          Create new schema for each VFR file
       --file      Path to xml.gz or URL list file
       --date      Date in format 'YYYYMMDD'
       --type      Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --layer     Import only selected layers separated by comma (if not given all layers are processed)
       --geom      Preferred geometry 'OriginalniHranice' or 'GeneralizovaneHranice' (if not found or not given than first geometry is used)
       --dbname    Output PostGIS database
       --schema    Schema name (default: public)
       --user      User name
       --passwd    Password
       --host      Host name
       --overwrite Overwrite existing PostGIS tables
       --append    Append to existing PostGIS tables

"""

import os
import sys
import atexit
import time
from getopt import GetoptError

from vfr4ogr.ogr import check_ogr, open_file, list_layers, convert_vfr, open_ds, print_summary
from vfr4ogr.vfr import Mode
from vfr4ogr.utils import fatal, message, parse_xml_gz, compare_list, error, check_log
from vfr4ogr.parse import parse_cmd
from vfr4ogr.pgutils import open_db, create_schema, check_epsg, create_indices

# print program usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()
    
    # parse cmdline arguments
    options = { 'dbname' : None, 'schema' : None, 'user' : None, 'passwd' : None, 'host' : None, 
                'overwrite' : False, 'extended' : False, 'layer' : [], 'geom' : None, 'download' : False,
                'schema_per_file' : False, 'append' : False, 'date' : None}
    try:
        filename = parse_cmd(sys.argv, "heodsa", ["help", "overwrite", "extended", "append",
                                              "file=", "date=", "type=", "layer=", "geom=",
                                              "dbname=", "schema=", "user=", "passwd=", "host="],
                             options)
    except GetoptError, e:
        usage()
        if str(e):
            fatal(e)
        else:
            sys.exit(0)

    # build dsn string and options
    lco_options = []
    odsn = ''
    conn = None
    if options['dbname']:
        odsn += "PG:dbname=%s" % options['dbname']
        if options['user']:
            odsn += " user=%s" % options['user']
        if options['passwd']:
            odsn += " password=%s" % options['passwd']
        if options['host']:
            odsn += " host=%s" % options['host']
        
        # open connection to DB
        conn = open_db(odsn[3:])
    
    # get list of input VFR file(s)
    file_list = open_file(filename, options['download'], force_date = options['date'])
    # get list of layers
    layer_list = options['layer']
    if layer_list:
        layer_list_all = layer_list
    else:
        layer_list_all = []
    schema_list = []
    
    epsg_checked = False
    append = options['append']
    ipass = 0
    stime = time.time()
    
    # process VFR file(s) and load them to DB
    for fname in file_list:
        message("Processing %s (%d out of %d)..." % (fname, ipass+1, len(file_list)))
        
        # open VFR file as OGR datasource
        ids = open_ds(fname)
        if ids is None:
            ipass += 1
            continue # unable to open - skip
        
        if not odsn:
            # no output datasource given -> list available layers and exit
            layer_list = list_layers(ids, options['extended'], sys.stdout)
            if options['extended'] and os.path.exists(filename):
                compare_list(layer_list, parse_xml_gz(filename))
        else:
            # check if EPSG 5514 exists in output DB (only first pass)
            if not epsg_checked:
                check_epsg(conn)
                epsg_checked = True
            
            # get list of layers
            if not options['layer']:
                for l in list_layers(ids, False, None):
                    if l not in layer_list_all:
                        layer_list_all.append(l)
            
            # build datasource string per file
            odsn_reset = odsn
            if options['schema_per_file'] or options['schema']:
                if options['schema_per_file']:
                    # set schema per file
                    schema_name = os.path.basename(fname).rstrip('.xml.gz').lower()
                    if schema_name[0].isdigit():
                        schema_name = 'vfr_' + schema_name
                else:
                    schema_name = options['schema'].lower()
                
                # create schema in output DB if needed
                create_schema(conn, schema_name)
                odsn += ' active_schema=%s' % schema_name
                if schema_name not in schema_list:
                    schema_list.append(schema_name)
            
            # check mode - process changes or append
            mode = Mode.write
            if fname.split('_')[-1][0] == 'Z':
                mode = Mode.change
            elif append:
                mode = Mode.append
            
            # do the conversion
            try:
                nfeat = convert_vfr(ids, odsn, "PostgreSQL", options['layer'],
                                    options['overwrite'], lco_options, options['geom'],
                                    mode, {'pgconn': conn})
            except RuntimeError as e:
                error("Unable to read %s: %s" % (fname, e))
            
            # reset datasource string per file
            if options['schema_per_file']:
                odsn = odsn_reset
            
            if nfeat > 0:
                append = True # append on next passes
        
        # close input VFR datasource
        ids.Destroy()
        ipass += 1
    
    # create indices for output tables
    if conn:
        create_indices(conn, schema_list, layer_list_all)
    
    # print final summary
    if (ipass > 1 and options.get('schema_per_file', False) is False) \
            or options.get('append', True):
        print_summary(odsn, "PostgreSQL", layer_list_all, stime)
    
    # close DB connection
    if conn:
        conn.close()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

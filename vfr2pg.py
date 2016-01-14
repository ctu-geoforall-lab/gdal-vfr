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
Imports VFR data to PostGIS database

Requires GDAL library version 1.11 or later.

One of input options must be given:
       --file
       --type

Usage: vfr2pg [-edsgl] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_XXXXXX_ABCD] [--layer=layer1,layer2,...]
                       [--geom=OriginalniHranice|GeneralizovaneHranice]
                       --dbname <database name>
                       [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]
                       [--overwrite] [--append]

       -e          Extended layer list statistics
       -d          Download VFR data to the currect directory (--type required) and exit
       -s          Create new schema for each VFR file
       -g          Skip features without geometry
       -l          List existing layers in output database and exit
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

import sys
import atexit
from getopt import GetoptError

from vfr4ogr import VfrPg
from vfr4ogr.parse import parse_cmd
from vfr4ogr.logger import check_log, VfrLogger
from vfr4ogr.exception import VfrError

# print program usage
def usage():
    print __doc__

def main():
    # parse cmdline arguments
    options = { 'dbname' : None, 'schema' : None, 'user' : None, 'passwd' : None, 'host' : None, 
                'overwrite' : False, 'extended' : False, 'layer' : [], 'geom' : None, 'download' : False,
                'schema_per_file' : False, 'append' : False, 'date' : None, 'nogeomskip': False, 'list' : False}
    try:
        file_list = parse_cmd(sys.argv, "haoedsgl", ["help", "overwrite", "extended", "append",
                                                     "file=", "date=", "type=", "layer=", "geom=",
                                                     "dbname=", "schema=", "user=", "passwd=", "host="],
                             options)
    except GetoptError as e:
        usage()
        if str(e):
            sys.exit(e)
        else:
            return 0
    except VfrError as e:
        sys.exit('ERROR: ' + str(e))
        
    # build datasource name
    odsn = None
    if options['dbname']:
        odsn = "PG:dbname=%s" % options['dbname']
        if options['user']:
            odsn += " user=%s" % options['user']
        if options['passwd']:
            odsn += " password=%s" % options['passwd']
        if options['host']:
            odsn += " host=%s" % options['host']

    # create convertor
    try:
        pg = VfrPg(schema=options['schema'], schema_per_file=options['schema_per_file'],
                   dsn=odsn, geom_name=options['geom'], layers=options['layer'],
                   nogeomskip=options['nogeomskip'], overwrite=options['overwrite'])
    except VfrError as e:
        sys.exit('ERROR: {}'.format(e))
    
    # write log process header
    pg.cmd_log(sys.argv)
    
    if options['list']:
        # list output database and exit
        pg.print_summary()
        return 0

    # read file list and download VFR files if needed
    try:
        pg.download(file_list, options['date'])
    except VfrError as e:
        VfrLogger.error(str(e))
    if options['download']:
        # download only requested, exiting
        return 0
    
    # import input VFR files to PostGIS
    ipass = pg.run(options['append'], options['extended'])
    
    # create indices for output tables
    pg.create_indices()
    
    # print final summary
    if (ipass > 1 and options.get('schema_per_file', False) is False) \
            or options.get('append', True):
        pg.print_summary()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

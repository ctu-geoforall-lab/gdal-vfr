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
"""

import sys
import atexit
import argparse

from vfr4ogr import VfrPg
from vfr4ogr.parse import parse_cmd
from vfr4ogr.logger import check_log, VfrLogger
from vfr4ogr.exception import VfrError, VfrErrorCmd

def parse_args():
    parser = argparse.ArgumentParser(prog="vfr2pg",
                                     description="Imports VFR data to PostGIS database. "
                                     "Requires GDAL library version 1.11 or later.")

    parser.add_argument("-e", "--extended",
                        action='store_true',
                        help="Extended layer list statistics")
    parser.add_argument("-d", "--download",
                        action='store_true',
                        help="Download VFR data to the currect directory (--type required) and exit")
    parser.add_argument("-s", "--fileschema",
                        action='store_true',
                        help="Create new schema for each VFR file")
    parser.add_argument("-g", "--nogeomskip",
                        action='store_true',
                        help="Skip features without geometry")
    parser.add_argument("-l", "--list",
                        action='store_true',
                        help="List existing layers in output database and exit")
    parser.add_argument("--file",
                        help="Path to xml.gz|zip or URL list file")
    parser.add_argument("--date",
                        help="Date in format 'YYYYMMDD'")
    parser.add_argument("--type",
                        help="Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'")
    parser.add_argument("--layer",
                        help="Import only selected layers separated by comma (if not given all layers are processed)")
    parser.add_argument("--geom",
                        help="Preferred geometry 'OriginalniHranice' or 'GeneralizovaneHranice' (if not found or not given than first geometry is used)")
    parser.add_argument("--dbname",
                        help="Output PostGIS database")
    parser.add_argument("--schema",
                        help="Schema name (default: public)")
    parser.add_argument("--user",
                        help="User name")
    parser.add_argument("--passwd",
                        help="Password")
    parser.add_argument("--host",
                        help="Host name")
    parser.add_argument("--port",
                        help="Port")
    parser.add_argument("-o", "--overwrite",
                        action='store_true',
                        help="Overwrite existing PostGIS tables")
    parser.add_argument("-a", "--append",
                        action='store_true',
                        help="Append to existing PostGIS tables")

    return parser.parse_args(), parser.print_help

def main():
    # parse cmdline arguments
    options, usage = parse_args()
    options.format = 'PostgreSQL'
    try:
        file_list = parse_cmd(options)
    except VfrErrorCmd as e:
        usage()
        sys.exit('ERROR: {}'.format(e))
        
    # build datasource name
    odsn = None
    if options.dbname:
        odsn = "PG:dbname=%s" % options.dbname
        if options.user:
            odsn += " user=%s" % options.user
        if options.passwd:
            odsn += " password=%s" % options.passwd
        if options.host:
            odsn += " host=%s" % options.host
        if options.port:
            odsn += " port=%s" % options.port

    # create convertor
    try:
        pg = VfrPg(schema=options.schema, schema_per_file=options.fileschema,
                   dsn=odsn, geom_name=options.geom, layers=options.layer,
                   nogeomskip=options.nogeomskip, overwrite=options.overwrite)
    except VfrError as e:
        sys.exit('ERROR: {}'.format(e))
    
    # write log process header
    pg.cmd_log(sys.argv)
    
    if options.list:
        # list output database and exit
        pg.print_summary()
        return 0

    # read file list and download VFR files if needed
    try:
        pg.download(file_list, options.date)
    except VfrError as e:
        VfrLogger.error(str(e))
    if options.download:
        # download only requested, exiting
        return 0
    
    # import input VFR files to PostGIS
    ipass = pg.run(options.append, options.extended)
    
    # create indices for output tables
    pg.create_indices()
    
    # print final summary
    if (ipass > 1 and options.fileschema is False) \
            or options.append:
        pg.print_summary()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

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

import os
import sys
import atexit
import argparse

from vfr4ogr import VfrOgr
from vfr4ogr.parse import parse_cmd
from vfr4ogr.logger import check_log, VfrLogger
from vfr4ogr.exception import VfrError, VfrErrorCmd

def parse_args():
    parser = argparse.ArgumentParser(prog="vfr2ogr",
                                     description="Converts VFR file into desired GIS format supported by OGR library."
                                     "Requires GDAL library version 1.11 or later.")

    parser.add_argument("-f", "--formats",
                        action='store_true',
                        help="List supported output formats")
    parser.add_argument("-e", "--extended",
                        action='store_true',
                        help="Extended layer list statistics")
    parser.add_argument("-d", "--download",
                        action='store_true',
                        help="Download VFR data to the currect directory (--type required) and exit")
    parser.add_argument("-g", "--nogeomskip",
                        action='store_true',
                        help="Skip features without geometry")
    parser.add_argument("-l", "--list",
                        action='store_true',
                        help="List existing layers in output datasource and exit")
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
    parser.add_argument("--format",
                        help="Output format")
    parser.add_argument("--dsn",
                        help="Output OGR datasource")
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
    try:
        file_list = parse_cmd(options)
    except VfrErrorCmd as e:
        usage()
        sys.exit('ERROR: {}'.format(e))
   
    # set up driver-specific options
    lco_options = []
    if options.format == 'SQLite':
        os.environ['OGR_SQLITE_SYNCHRONOUS'] = 'OFF'
    elif options.format == 'ESRI Shapefile':
        lco_options.append('ENCODING=UTF-8')

    # create convertor
    ogr = VfrOgr(frmt=options.format, dsn=options.dsn,
                 geom_name=options.geom, layers=options.layer,
                 nogeomskip=options.nogeomskip, overwrite=options.overwrite,
                 lco_options=lco_options)

    # write log process header
    ogr.cmd_log(sys.argv)
    
    if options.list:
        # list output datasource and exit
        ogr.print_summary()
        return 0

    # read file list and download VFR files if needed
    ogr.download(file_list, options.date)
    if options.download:
        # download only requested, exiting
        return 0
    
    # import VFR files
    ipass = ogr.run()

    # print final summary
    if ipass > 1 or options.append:
        ogr.print_summary()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

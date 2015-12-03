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
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL library version 1.11 or later.

One of input options must be given:
       --file
       --type

Usage: vfr2ogr [-fedgl] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_000000_ABCD] [--layer=layer1,layer2,...]
                        [--geom=OriginalniHranice|GeneralizovaneHranice]
                        [--format=<output format>] [--dsn=<OGR datasource>]
                        [--overwrite] [--append]

       -f          List supported output formats
       -e          Extended layer list statistics 
       -d          Download VFR data to the currect directory (--type required)
       -g          Skip features without geometry
       -l          List existing layers in output datasource and exit
       --file      Path to xml.gz or URL list file
       --date      Date in format 'YYYYMMDD'
       --type      Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --layer     Import only selected layers separated by comma (if not given all layers are processed)
       --geom      Preferred geometry 'OriginalniHranice' or 'GeneralizovaneHranice' (if not found or not given than first geometry is used)
       --format    Output format
       --dsn       Output OGR datasource
       --overwrite Overwrite existing files
       --append    Append to existing files

"""

import os
import sys
import atexit
from getopt import GetoptError

from vfr4ogr import VfrOgr
from vfr4ogr.parse import parse_cmd
from vfr4ogr.logger import check_log, VfrLogger
from vfr4ogr.exception import VfrError

# print usage
def usage():
    print __doc__

def main():
    # parse cmd arguments
    options = { 'format' : None, 'dsn' : None, 'overwrite' : False, 'extended' : False,
                'layer' : [], 'geom' : None, 'download' : False, 'append' : False, 'date' : None,
                'nogeomskip': False, 'list' : False}
    try:
        file_list = parse_cmd(sys.argv, "haofedgl", ["help", "overwrite", "extended", "append",
                                                     "file=", "date=", "type=", "layer=", "geom=",
                                                     "format=", "dsn="],
                              options)
    except GetoptError as e:
        usage()
        if str(e):
            sys.exit('ERROR: ' + str(e))
        else:
            return 0
    except VfrError as e:
        sys.exit('ERROR: ' + str(e))
    
    # set up driver-specific options
    lco_options = []
    if options['format'] == 'SQLite':
        os.environ['OGR_SQLITE_SYNCHRONOUS'] = 'OFF'
    elif options['format'] == 'ESRI Shapefile':
        lco_options.append('ENCODING=UTF-8')

    # create convertor
    ogr = VfrOgr(frmt=options['format'], dsn=options['dsn'],
                 geom_name=options['geom'], layers=options['layer'],
                 nogeomskip=options['nogeomskip'], overwrite=options['overwrite'],
                 lco_options=lco_options)

    # write log process header
    ogr.cmd_log(sys.argv)
    
    if options['list']:
        # list output datasource and exit
        ogr.print_summary()
        return 0

    # read file list and download VFR files if needed
    ogr.read_file_list(file_list)
    if options['download']:
        # download only requested, exiting
        return 0
    
    # import VFR files
    ipass = ogr.run()

    # print final summary
    if ipass > 1 or options.get('append', True):
        ogr.print_summary()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

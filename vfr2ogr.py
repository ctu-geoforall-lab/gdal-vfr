#!/usr/bin/env python

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
       -d          Download VFR data in currect directory (--type required)
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

import sys
import atexit
from getopt import GetoptError

from vfr4ogr import VfrOgr
from vfr4ogr.parse import parse_cmd
from vfr4ogr.logger import check_log

# print usage
def usage():
    print __doc__

def main():
    # parse cmd arguments
    options = { 'format' : None, 'dsn' : None, 'overwrite' : False, 'extended' : False,
                'layer' : [], 'geom' : None, 'download' : False, 'append' : False, 'date' : None,
                'nogeomskip': False, 'list' : False}
    try:
        filename = parse_cmd(sys.argv, "haofedgl", ["help", "overwrite", "extended", "append",
                                                    "file=", "date=", "type=", "layer=", "geom=",
                                                    "format=", "dsn="], options)
    except GetoptError, e:
        usage()
        if str(e):
            sys.exit(e)
        else:
            return 0

    # set up driver-specific options
    lco_options = []
    if options['format'] == 'SQLite':
        os.environ['OGR_SQLITE_SYNCHRONOUS'] = 'OFF'
    elif options['format'] == 'ESRI Shapefile':
        lco_options.append('ENCODING=UTF-8')
   
    ogr = VfrOgr(options['format'], options['dsn'],
                 options['geom'], options['layer'], options['nogeomskip'],
                 options['overwrite'], lco_options)

   # list output datasource and exit
    if options['list']:
        ogr.print_summary()
        return 0

    # get list of input VFR file(s)
    ogr.open_file(filename)
    if options['download']:
        return 0
    
    # import VFR files
    ipass = ogr.run()
        
    if ipass > 1 or options.get('append', True):
        ogr.print_summary()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

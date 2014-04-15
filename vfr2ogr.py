#!/usr/bin/env python

"""
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL/OGR library version 1.11 or later.

One of options must be given:
       --file
       --date and --ftype

Usage: vfr2ogr.py [-f] [-o] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_000000_ABCD] [--layer=layer1,layer2,...] [--format=<output format>] [--dsn=<OGR datasource>] 

       -f         List supported output formats
       -e         Extended layer list statistics 
       -o         Overwrite existing files
       --file     Path to xml.gz file
       --date     Date in format 'YYYYMMDD'
       --type     Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --layer    Import only selected layers separated by comma (if not given all layers are processed)
       --format   Output format
       --dsn      Output OGR datasource
"""

import sys
from getopt import GetoptError

from vfr2ogr.ogr import check_ogr, open_file, list_layers, convert_vfr
from vfr2ogr.utils import fatal, message, parse_xml_gz, compare_list
from vfr2ogr.parse import parse_cmd

# print usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()

    # parse cmd arguments
    options = { 'format' : None, 'dsn' : None, 'overwrite' : False, 'extended' : False,
                'layer' : []}
    try:
        filename = parse_cmd(sys.argv, "hfeo", ["help", "overwrite", "extended",
                                               "file=", "date=", "type=", "layer=",
                                               "format=", "dsn="], options)
    except GetoptError, e:
        usage()
        fatal(e)

    # open input file by GML driver
    ids = open_file(filename)
    
    if options['format'] is None:
        # list available layers and exit
        layer_list = list_layers(ids, options['extended'])
        if options['extended']:
            compare_list(layer_list, parse_xml_gz(filename))
    else:
        if options['dsn'] is None:
            fatal("Output datasource not defined")
        else:
            # convert VFR ...
            time = convert_vfr(ids, options['dsn'], options['format'], options['layer'], options['overwrite'])
            message("Time elapsed: %d sec" % time)
    
    ids.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python

"""
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL/OGR library version 1.11 or later.

One of options must be given:
       --file
       --date and --ftype

Usage: vfr2ogr.py [-f] [-o] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--ftype=ST_ABCD|OB_000000_ABCD] [--format=<output format>] [--dsn=<OGR datasource>]

       -f         List supported output formats
       -o         Overwrite existing files
       --file     Path to xml.gz file
       --date     Date in format 'YYYYMMDD'
       --ftype    Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --format   Output format
       --dsn      Output OGR datasource
"""

from vfr2ogr.vfr import *
from vfr2ogr.utils import *
from vfr2ogr.parse import parse_cmd

# print usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()

    # parse cmd arguments
    options = { 'format' : None, 'dsn' : None, 'overwrite' : False }
    filename = parse_cmd(sys.argv, "hfo", ["help", "overwrite",
                                "file=", "date=", "type=",
                                "format=", "dsn="], options)
    if not filename:
        usage()
        sys.exit(1)
    
    # open input file by GML driver
    ids = open_file(filename)
    
    if options['format'] is None:
        # list available layers and exit
        list_layers(ids)
    else:
        if options['dsn'] is None:
            fatal("Output datasource not defined")
        else:
            # convert VFR ...
            time = convert_vfr(ids, options['dsn'], options['format'], options['overwrite'])
            message("Time elapsed: %d sec" % time)
    
    ids.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

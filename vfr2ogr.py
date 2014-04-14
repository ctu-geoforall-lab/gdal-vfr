#!/usr/bin/env python

"""
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL/OGR library version 1.11 or later.

One of options must be given:
       --file
       --date and --ftype

Usage: vfr2ogr.py [-f] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--ftype=ST_ABCD|OB_000000_ABCD] [--format=<output format>] [--dsn=<OGR datasource>]

       -f         List supported output formats
       -o         Overwrite existing files
       --file     Path to xml.gz file
       --date     Date in format YYYYMMDD
       --ftyoe    Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --format   Output format
       --dsn      Output OGR datasource
"""

import getopt

from vfr2ogr.vfr import *

# print usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()
    
    if len(sys.argv) < 2: # at least one argument required (-f or filename)
        usage()
        sys.exit(2)
        
    # parse options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hfo", ["help", "overwrite", "file=", "date=", "type=", "format=", "dsn="])
    except getopt.GetoptError as err:
        print str(err) 
        usage()
        sys.exit(2)
    
    overwrite = False
    filename = date = ftype = None
    oformat = odsn = None
    for o, a in opts:
        if o == "--file":
            filename = a
        elif o == "--date":
            date = a
        elif o == "--type":
            ftype = a
        elif o in ("-o",  "--overwrite"):
            overwrite = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o == "-f": # unused
            list_formats()
            sys.exit(0)
        elif o == "--format":
            oformat = a
        elif o == "--dsn":
            odsn = a
        else:
            assert False, "unhandled option"
    
    if not filename and not date:
        fatal("--file or --date requested")
    if filename and date:
        fatal("--file and --date are mutually exclusive")
    if date and not ftype:
        fatal("--ftype requested")
    
    if filename:
        # check if input VFR file exists
        filename = check_file(filename)
    else:
        url = "http://vdp.cuzk.cz/vymenny_format/soucasna/%s_%s.xml.gz" % (date, ftype)
        message("Downloading %s..." % url)
        filename = "/vsicurl/" + url
    
    # open input file by GML driver
    ids = open_file(filename)
    
    if oformat is None:
        list_layers(ids)
    else:
        if odsn is None:
            fatal("Output datasource not defined")
        else:
            time = convert_vfr(ids, odsn, oformat, overwrite)
            message("Time elapsed: %d sec" % time)
    
    ids.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

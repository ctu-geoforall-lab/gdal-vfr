#!/usr/bin/env python

"""
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL/OGR library version 1.11 or later.

Usage: vfr2ogr.py [-f] /path/to/vfr/filename [--format=<output format>] [--dsn=<OGR datasource>]

       -f         List supported output formats
       -o         Overwrite existing files
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
        
    if sys.argv[1] == '-f':
        list_formats()
        sys.exit(0)

    # check if input VFR file exists
    filename = check_file(sys.argv[1])
    
    # parse options
    try:
        opts, args = getopt.getopt(sys.argv[2:], "hfo", ["help", "overwrite", "format=", "dsn="])
    except getopt.GetoptError as err:
        print str(err) 
        usage()
        sys.exit(2)
    
    overwrite = False
    oformat = odsn = None
    for o, a in opts:
        if o in ("-o",  "--overwrite"):
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

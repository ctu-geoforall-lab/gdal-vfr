#!/usr/bin/env python

"""
Imports VFR data to PostGIS database

Requires GDAL/OGR library version 1.11 or later.

Usage: vfr2py.py [-f] [-o] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--ftype=ST_ABCD|OB_000000_ABCD] --dbname <database name>  [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]

       -o         Overwrite existing PostGIS tables
       -e         Extended layer list statistics 
       --file     Path to xml.gz file
       --date     Date in format 'YYYYMMDD'
       --ftype    Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --dbname   Output PostGIS database
       --schema   Schema name (default: public)
       --user     User name
       --passwd   Password
       --host     Host name
"""

import sys
from getopt import GetoptError

from vfr2ogr.ogr import check_ogr, open_file, list_layers, convert_vfr
from vfr2ogr.utils import fatal, message
from vfr2ogr.parse import parse_cmd

# print usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()
    
    # parse cmd arguments
    options = { 'dbname' : None, 'schema' : None, 'user' : None, 'passwd' : None, 'host' : None, 
                'overwrite' : False, 'extended' : False }
    try:
        filename = parse_cmd(sys.argv, "heo", ["help", "overwrite", "extended",
                                              "file=", "date=", "type=",
                                              "dbname=", "schema=", "user=", "passwd=", "host="],
                             options)
    except GetoptError, e:
        usage()
        fatal(e)
    
    # open input file by GML driver
    ids = open_file(filename)
    
    if options['dbname'] is None:
        # list available layers and exit
        list_layers(ids, options['extended'])
    else:
        odsn = "PG:dbname=%s" % options['dbname']
        if options['user']:
            odsn += " user=%s" % options['user']
        if options['passwd']:
            odsn += " passwd=%s" % options['passwd']
        if options['host']:
            odsn += " host=%s" % options['host']
        
        lco_options = ["GEOMETRY_NAME=definicnibod"] # TODO: fix GDAL/OGR
        if options['schema']:
            lco_options.append('SCHEMA=%s' % schema)
        
        time = convert_vfr(ids, odsn, "PostgreSQL", options['overwrite'], lco_options)
        message("Time elapsed: %d sec" % time)
    
    ids.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

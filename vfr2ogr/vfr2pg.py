#!/usr/bin/env python

"""
Imports VFR data to PostGIS database

Requires GDAL/OGR library version 1.11 or later.

Usage: vfr2py.py /path/to/vfr/filename --dbname <database name>  [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]

       --dbname Output PostGIS database
       --schema Schema name (default: public)
       --user   User name
       --passwd Password
       --host   Host name
"""

import getopt

from vfr import *

# print usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()
    
    if len(sys.argv) < 2: # at least one argument required (filename)
        usage()
        sys.exit(2)
    
    # check if input VFR file exists
    filename = check_file(sys.argv[1])
    
    # parse options
    try:
        opts, args = getopt.getopt(sys.argv[2:], "hfvo", ["help", "verbose", "overwrite",
                                                          "dbname=", "schema=", "user=", "passwd=", "host="])
    except getopt.GetoptError as err:
        print str(err) 
        usage()
        sys.exit(2)
    
    verbose = overwrite = False
    dbname = schema = user = passwd = host = None
    for o, a in opts:
        if o in ("-o",  "--overwrite"):
            overwrite = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o == "--dbname":
            dbname =a
        elif o == "--schema":
            schema = a
        elif o == "--user":
            user = a
        elif o == "--passwd":
            passwd = a
        elif o == "--host":
            host = a
        else:
            assert False, "unhandled option"
    
    # open input file by GML driver
    ids = open_file(filename)
    
    if dbname is None:
        list_layers(ids)
    else:
        odsn = "PG:dbname=%s" % dbname
        if user:
            odsn += " user=%s" % user
        if passwd:
            odsn += " passwd=%s" % passwd
        if host:
            odsn += " host=%s" % host
        
        options = ["GEOMETRY_NAME=definicnibod"] # TODO: fix GDAL/OGR
        if schema:
            options.append('SCHEMA=%s' % schema)
        
        time = convert_vfr(ids, odsn, "PostgreSQL", overwrite, options)
        message("Time elapsed: %d sec" % time)
    
    ids.Destroy()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

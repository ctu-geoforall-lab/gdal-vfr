#!/usr/bin/env python

"""
Imports VFR data to PostGIS database

Requires GDAL/OGR library version 1.11 or later.

One of input options must be given:
       --file
       --date and --type

Usage: vfr2py.py [-f] [-o] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_000000_ABCD] [--layer=layer1,layer2,...]  [--geom=OriginalniHranice|GeneralizovaneHranice]
                            --dbname <database name>
                            [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]
                            

       -o         Overwrite existing PostGIS tables
       -e         Extended layer list statistics
       --file     Path to xml.gz file
       --date     Date in format 'YYYYMMDD'
       --type     Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --layer    Import only selected layers separated by comma (if not given all layers are processed)
       --geom     Preferred geometry column 'OriginalniHranice' or 'GeneralizovaneHranice' (if not found or given than first column is used)
       --dbname   Output PostGIS database
       --schema   Schema name (default: public)
       --user     User name
       --passwd   Password
       --host     Host name
"""

import os
import sys
import atexit
from getopt import GetoptError

from vfr2ogr.ogr import check_ogr, open_file, list_layers, convert_vfr, check_log
from vfr2ogr.utils import fatal, message, parse_xml_gz, compare_list
from vfr2ogr.parse import parse_cmd

# print usage
def usage():
    print __doc__

def check_epsg(conn_string):
    try:
        import psycopg2
    except ImportError as e:
        sys.stderr.write("Unable to add EPSG 5514: %s\n" % e)
        return
    
    try:
        conn = psycopg2.connect(conn_string)
    except psycopg2.OperationalError as e:
        sys.exit("Unable to connect to DB: %s" % e)
    
    cursor = conn.cursor()
    cursor.execute("SELECT srid FROM spatial_ref_sys WHERE srid = 5514")
    epsg_exists = bool(cursor.fetchall())
    if not epsg_exists:
        stmt = """INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) VALUES ( 5514, 'EPSG', 5514, '+proj=krovak +lat_0=49.5 +lon_0=24.83333333333333 +alpha=30.28813972222222 +k=0.9999 +x_0=0 +y_0=0 +ellps=bessel +towgs84=589,76,480,0,0,0,0 +units=m +no_defs ', 'PROJCS["S-JTSK / Krovak East North",GEOGCS["S-JTSK",DATUM["System_Jednotne_Trigonometricke_Site_Katastralni",SPHEROID["Bessel 1841",6377397.155,299.1528128,AUTHORITY["EPSG","7004"]],TOWGS84[589,76,480,0,0,0,0],AUTHORITY["EPSG","6156"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4156"]],PROJECTION["Krovak"],PARAMETER["latitude_of_center",49.5],PARAMETER["longitude_of_center",24.83333333333333],PARAMETER["azimuth",30.28813972222222],PARAMETER["pseudo_standard_parallel_1",78.5],PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],AUTHORITY["EPSG","5514"]]')"""
        cursor.execute(stmt)
        conn.commit()
        message("EPSG 5514 defined in DB")
    
    cursor.close()
    conn.close()

def main():
    # check requirements
    check_ogr()
    
    # parse cmd arguments
    options = { 'dbname' : None, 'schema' : None, 'user' : None, 'passwd' : None, 'host' : None, 
                'overwrite' : False, 'extended' : False, 'layer' : [], 'geom' : None}
    try:
        filename = parse_cmd(sys.argv, "heo", ["help", "overwrite", "extended",
                                              "file=", "date=", "type=", "layer=", "geom=",
                                              "dbname=", "schema=", "user=", "passwd=", "host="],
                             options)
    except GetoptError, e:
        usage()
        if str(e):
            fatal(e)
        else:
            sys.exit(0)
    
    # open input file by GML driver
    ids = open_file(filename)
    
    if options['dbname'] is None:
        # list available layers and exit
        layer_list = list_layers(ids, options['extended'])
        if options['extended'] and os.path.exists(filename):
            compare_list(layer_list, parse_xml_gz(filename))
    else:
        odsn = "PG:dbname=%s" % options['dbname']
        if options['user']:
            odsn += " user=%s" % options['user']
        if options['passwd']:
            odsn += " password=%s" % options['passwd']
        if options['host']:
            odsn += " host=%s" % options['host']
        
        lco_options = ["PG_USE_COPY=YES"]
        if options['schema']:
            lco_options.append('SCHEMA=%s' % schema)
        
        # check EPSG 5514
        check_epsg(odsn[3:])
        
        time = convert_vfr(ids, odsn, "PostgreSQL", options['layer'], options['overwrite'], lco_options, options['geom'])
        message("Time elapsed: %d sec" % time)
    
    ids.Destroy()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

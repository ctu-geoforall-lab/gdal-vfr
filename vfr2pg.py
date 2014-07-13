#!/usr/bin/env python

"""
Imports VFR data to PostGIS database

Requires GDAL/OGR library version 1.11 or later.

One of input options must be given:
       --file
       --type

Usage: vfr2py [-e] [-d] [-s] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_XXXXXX_ABCD] [--layer=layer1,layer2,...] [--geom=OriginalniHranice|GeneralizovaneHranice]
                              --dbname <database name>
                             [--schema <schema name>] [--user <user name>] [--passwd <password>] [--host <host name>]
                             [--overwrite] [--append]

       -e          Extended layer list statistics
       -d          Save downloaded VFR data in currect directory (--type required)
       -s          Create new schema for each VFR file
       --file      Path to xml.gz or URL list file
       --date      Date in format 'YYYYMMDD'
       --type      Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --layer     Import only selected layers separated by comma (if not given all layers are processed)
       --geom      Preferred geometry 'OriginalniHranice' or 'GeneralizovaneHranice' (if not found or not given than first geometry is used)
       --dbname    Output PostGIS database
       --schema    Schema name (default: public)
       --user      User name
       --passwd    Password
       --host      Host name
       --overwrite Overwrite existing PostGIS tables
       --append    Append to existing PostGIS tables

"""

import os
import sys
import atexit
import time
from getopt import GetoptError

from vfr4ogr.ogr import check_ogr, open_file, list_layers, convert_vfr, check_log, open_ds, print_summary, Mode
from vfr4ogr.utils import fatal, message, parse_xml_gz, compare_list, error
from vfr4ogr.parse import parse_cmd

# print usage
def usage():
    print __doc__

def open_db(conn_string):
    try:
        import psycopg2
    except ImportError as e:
        return None
    
    try:
        conn = psycopg2.connect(conn_string)
    except psycopg2.OperationalError as e:
        sys.exit("Unable to connect to DB: %s\nTry to define --user and/or --passwd" % e)
    
    return conn

def create_schema(conn, name):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name = '%s'" % name)
        if not bool(cursor.fetchall()):
            # cursor.execute("CREATE SCHEMA IF NOT EXISTS %s" % name)
            cursor.execute("CREATE SCHEMA %s" % name)
            conn.commit()
    except StandardError as e:
        sys.exit("Unable to create schema %s: %s" % (name, e))
    
    cursor.close()

def check_epsg(conn):
    if not conn:
        sys.stderr.write("Unable to add EPSG 5514: %s\n" % e)
        return
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT srid FROM spatial_ref_sys WHERE srid = 5514")
    except StandardError as e:
        sys.exit("PostGIS doesn't seems to be activated. %s" % e)
        
    epsg_exists = bool(cursor.fetchall())
    if not epsg_exists:
        stmt = """INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) VALUES ( 5514, 'EPSG', 5514, '+proj=krovak +lat_0=49.5 +lon_0=24.83333333333333 +alpha=30.28813972222222 +k=0.9999 +x_0=0 +y_0=0 +ellps=bessel +towgs84=589,76,480,0,0,0,0 +units=m +no_defs ', 'PROJCS["S-JTSK / Krovak East North",GEOGCS["S-JTSK",DATUM["System_Jednotne_Trigonometricke_Site_Katastralni",SPHEROID["Bessel 1841",6377397.155,299.1528128,AUTHORITY["EPSG","7004"]],TOWGS84[589,76,480,0,0,0,0],AUTHORITY["EPSG","6156"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4156"]],PROJECTION["Krovak"],PARAMETER["latitude_of_center",49.5],PARAMETER["longitude_of_center",24.83333333333333],PARAMETER["azimuth",30.28813972222222],PARAMETER["pseudo_standard_parallel_1",78.5],PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],AUTHORITY["EPSG","5514"]]')"""
        cursor.execute(stmt)
        conn.commit()
        message("EPSG 5514 defined in DB")
    
    cursor.close()

def create_indices(conn, layer_list):
    if not conn:
        sys.stderr.write("Unable to connect DB\n")
        return

    column = "gml_id"
    
    cursor = conn.cursor()
    for layer in layer_list:
        table = layer.lower()
        cursor.execute('BEGIN')
        try:
            cursor.execute("CREATE INDEX %s_%s_idx ON %s (%s)" % \
                               (table, column, table, column))
            cursor.execute('COMMIT')
        except StandardError as e:
            sys.stderr.write("Unable to create index %s_%s: %s\n" % (table, column, e))
            cursor.execute('ROLLBACK')

    cursor.close()
    
def main():
    # check requirements
    check_ogr()
    
    # parse cmd arguments
    options = { 'dbname' : None, 'schema' : None, 'user' : None, 'passwd' : None, 'host' : None, 
                'overwrite' : False, 'extended' : False, 'layer' : [], 'geom' : None, 'download' : False,
                'schema_per_file' : False, 'append' : False, 'date' : None}
    try:
        filename = parse_cmd(sys.argv, "heodsa", ["help", "overwrite", "extended", "append",
                                              "file=", "date=", "type=", "layer=", "geom=",
                                              "dbname=", "schema=", "user=", "passwd=", "host="],
                             options)
    except GetoptError, e:
        usage()
        if str(e):
            fatal(e)
        else:
            sys.exit(0)

    # build dsn string and options
    ### lco_options = ["PG_USE_COPY=YES"]
    lco_options = []
    odsn = ''
    conn = None
    if options['dbname']:
        odsn += "PG:dbname=%s" % options['dbname']
        if options['user']:
            odsn += " user=%s" % options['user']
        if options['passwd']:
            odsn += " password=%s" % options['passwd']
        if options['host']:
            odsn += " host=%s" % options['host']

        # open connection to DB
        conn = open_db(odsn[3:])
    
    # get list of input VFR files
    file_list  = open_file(filename, options['download'], force_date = options['date'])
    layer_list = options['layer']
    
    epsg_checked = False
    append = options['append']
    ipass = 0
    stime = time.time()
    
    # go thru VFR file and load them to DB
    for fname in file_list:
        message("Processing %s (%d out of %d)..." % (fname, ipass+1, len(file_list)))

        # open OGR datasource
        ids = open_ds(fname)
        if ids is None:
            ipass += 1
            continue # unable to open - skip
        
        if not odsn:
            # list available layers and exit
            layer_list = list_layers(ids, options['extended'], sys.stdout)
            if options['extended'] and os.path.exists(filename):
                compare_list(layer_list, parse_xml_gz(filename))
        else:
            # check EPSG 5514 (only first pass)
            if not epsg_checked:
                check_epsg(conn)
                epsg_checked = True
            
            if not layer_list:
                layer_list = list_layers(ids, False, None)
            
            # build datasource string
            odsn_reset = odsn
            if options['schema_per_file'] or options['schema']:
                if options['schema_per_file']:
                    # set schema per file
                    schema_name = os.path.basename(fname).rstrip('.xml.gz').lower()
                    if schema_name[0].isdigit():
                        schema_name = 'vfr_' + schema_name
                else:
                    schema_name = options['schema'].lower()
                
                create_schema(conn, schema_name)
                odsn += ' active_schema=%s' % schema_name
            
            # do the conversion
            if fname.split('_')[-1][0] == 'Z':
                mode = Mode.change
            elif append:
                mode = Mode.append
            try:
                nfeat = convert_vfr(ids, odsn, "PostgreSQL", options['layer'],
                                    options['overwrite'], lco_options, options['geom'],
                                    mode)
            except RuntimeError as e:
                error("Unable to read %s: %s" % (fname, e))
            
            if options['schema_per_file']:
                odsn = odsn_reset
            
            if nfeat > 0:
                append = True # append on next passes
        
            
        ids.Destroy()
        ipass += 1
   
    # create indices
    create_indices(conn, layer_list)
    
    # print summary
    if (ipass > 1 and options.get('schema_per_file', False) is False) \
            or options.get('append', True):
        print_summary(odsn, "PostgreSQL", layer_list, stime)
    
    if conn:
        conn.close()
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

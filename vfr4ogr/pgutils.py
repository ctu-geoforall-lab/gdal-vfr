import sys

from utils import message

# open connection to output DB
def open_db(conn_string):
    try:
        import psycopg2
    except ImportError as e:
        sys.exit(e)
    
    try:
        conn = psycopg2.connect(conn_string)
    except psycopg2.OperationalError as e:
        sys.exit("Unable to connect to DB: %s\nTry to define --user and/or --passwd" % e)

    # check if PostGIS is installed
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT postgis_version()")
    except StandardError as e:
        sys.exit("ERROR: PostGIS doesn't seems to be installed.\n\n%s" % e)
        
    cursor.close()
    
    return conn

# create output schema if not exists
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

# insert EPSG 5514 definition into output DB if not defined
def check_epsg(conn):
    if not conn:
        return
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT srid FROM spatial_ref_sys WHERE srid = 5514")
    except StandardError as e:
        sys.exit("PostGIS doesn't seems to be activated. %s" % e)
        
    epsg_exists = bool(cursor.fetchall())
    if not epsg_exists:
        stmt = """INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) VALUES ( 5514, 'EPSG', 5514, '+proj=krovak +lat_0=49.5 +lon_0=24.83333333333333 +alpha=30.28813972222222 +k=0.9999 +x_0=0 +y_0=0 +ellps=bessel +towgs84=570.8,85.7,462.8,4.998,1.587,5.261,3.56 +units=m +no_defs ', 'PROJCS["S-JTSK / Krovak East North",GEOGCS["S-JTSK",DATUM["System_Jednotne_Trigonometricke_Site_Katastralni",SPHEROID["Bessel 1841",6377397.155,299.1528128,AUTHORITY["EPSG","7004"]],TOWGS84[570.8,85.7,462.8,4.998,1.587,5.261,3.56],AUTHORITY["EPSG","6156"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4156"]],PROJECTION["Krovak"],PARAMETER["latitude_of_center",49.5],PARAMETER["longitude_of_center",24.83333333333333],PARAMETER["azimuth",30.28813972222222],PARAMETER["pseudo_standard_parallel_1",78.5],PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],AUTHORITY["EPSG","5514"]]')"""
        cursor.execute(stmt)
        conn.commit()
        message("EPSG 5514 defined in DB")
    
    cursor.close()

# create indices for output tables (gml_id)
def create_indices(conn, schema_list, layer_list):
    if not conn:
        sys.stderr.write("Unable to connect DB\n")
        return
    
    if not schema_list:
        schema_list = ['public']
    
    column = "gml_id"
    
    cursor = conn.cursor()
    for schema in schema_list:
        for layer in layer_list:
            if layer == 'ZaniklePrvky':
                # skip deleted features
                continue
            
            if '.' in layer:
                schema, table = map(lambda x: x.lower(), layer.split('.', 1))
            else:
                table = layer.lower()
            
            indexname = "%s_%s_idx" % (table, column)
            cursor.execute("SELECT COUNT(*) FROM pg_indexes WHERE "
                           "tablename = '%s' and schemaname = '%s' and "
                           "indexname = '%s'" % (table, schema, indexname))
            if cursor.fetchall()[0][0] > 0:
                continue # indices for specified table already exists
        
            cursor.execute('BEGIN')
            try:
                cursor.execute("CREATE INDEX %s ON %s.%s (%s)" % \
                                   (indexname, schema, table, column))
                cursor.execute('COMMIT')
            except StandardError as e:
                sys.stderr.write("Unable to create index %s_%s: %s\n" % (table, column, e))
                cursor.execute('ROLLBACK')

    cursor.close()

# update fid sequence
def update_fid_seq(conn, table, fid, column = 'ogc_fid'):
    if not conn:
        sys.stderr.write("Unable to update FID sequence for table '%s'\n" % table)
        return
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT setval('%s_%s_seq', %d)" % (table, column, fid))
    except StandardError as e:
        sys.stderr.write("Unable to update FID sequence for table '%s': %s\n" % (table, e))
    
    cursor.close()

# get max fid
def get_fid_max(conn, table, column='ogc_fid'):
    if not conn:
        sys.stderr.write("No DB connection defined.\n" % table)
        return
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT max(%s) FROM %s" % (column, table))
    except StandardError as e:
        cursor.execute('ROLLBACK')
        cursor.close()
        return -1
    
    try:
        fid_max = int(cursor.fetchall()[0][0])
    except TypeError:
        fid_max = -1
    
    cursor.close()
    
    return fid_max

def build_dsn(options):
    if not options['dbname']:
        return None
    
    odsn = "PG:dbname=%s" % options['dbname']
    if options['user']:
        odsn += " user=%s" % options['user']
    if options['passwd']:
        odsn += " password=%s" % options['passwd']
    if options['host']:
        odsn += " host=%s" % options['host']
    
    return odsn

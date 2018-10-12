###############################################################################
#
# VFR importer based on GDAL library
#
# Author: Martin Landa <landa.martin gmail.com>
#
# Licence: MIT/X
#
###############################################################################

import sys

from .vfrogr import VfrOgr, Mode
from .logger import VfrLogger
from .exception import VfrError

class VfrPg(VfrOgr):
    def __init__(self, schema='public', schema_per_file=False, **kwargs):
        """Class for importing VFK data into PostGIS database.

        @param schema: name of schema where to import data
        @param schema_per_file: True to create for each file separate schema
        @param args: other argumenets, see VfrOgr class for details
        """
        if kwargs['dsn']:
            self._logFile = 'vfr2pg-{}'.format(self._get_dbname(kwargs['dsn']))
        else:
            self._logFile = 'vfr2pg'
        VfrOgr.__init__(self, "PostgreSQL", **kwargs)
        self._schema = schema
        self._schema_per_file = schema_per_file
        
        # build dsn string and options
        self._lco_options = []
        if self.odsn:
            # open connection to DB
            self._conn = self._opendb(self.odsn[3:])
        else:
            self._conn = None
        self.schema_list = None
                
    def __del__(self):
        self._conn.close()

    def _get_dbname(self, dsn):
        """Get dbname from datasource string

        @param dsn: datasource name
        """
        try:
            return dsn[dsn.find('dbname'):].split(' ')[0].strip().split('=')[1]
        except:
            raise VfrError("Unable to get DB name")
        
    def _opendb(self, conn_string):
        """Open DB connection.

        @param conn_string: PG connection string
        """
        try:
            import psycopg2
        except ImportError as e:
            raise VfrError(e)
            
        try:
            conn = psycopg2.connect(conn_string)
        except psycopg2.OperationalError as e:
            raise VfrError("Unable to connect to DB: %s\nTry to define --user and/or --passwd" % e)

        # check if PostGIS is installed
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT postgis_version()")
        except StandardError as e:
            raise VfrError("PostGIS doesn't seems to be installed.\n\n%s" % e)
            
        cursor.close()
        
        return conn

    def _create_schema(self, name):
        """Create output schema if not exists.

        @param name: name of schema to be created
        """
        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT schema_name FROM information_schema.schemata "
                            "WHERE schema_name = '%s'" % name)
            if not bool(cursor.fetchall()):
                # cursor.execute("CREATE SCHEMA IF NOT EXISTS %s" % name)
                cursor.execute("CREATE SCHEMA %s" % name)
                self._conn.commit()
        except StandardError as e:
            raise VfrError("Unable to create schema %s: %s" % (name, e))

        cursor.close()

    def _check_epsg(self):
        """Insert EPSG 5514 definition into output DB if not defined.
        """
        if not self._conn:
            return

        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT srid FROM spatial_ref_sys WHERE srid = 5514")
        except StandardError as e:
            raise VfrError("PostGIS doesn't seems to be activated. %s" % e)

        epsg_exists = bool(cursor.fetchall())
        if not epsg_exists:
            stmt = """INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext) VALUES ( 5514, 'EPSG', 5514, '+proj=krovak +lat_0=49.5 +lon_0=24.83333333333333 +alpha=30.28813972222222 +k=0.9999 +x_0=0 +y_0=0 +ellps=bessel +towgs84=570.8,85.7,462.8,4.998,1.587,5.261,3.56 +units=m +no_defs ', 'PROJCS["S-JTSK / Krovak East North",GEOGCS["S-JTSK",DATUM["System_Jednotne_Trigonometricke_Site_Katastralni",SPHEROID["Bessel 1841",6377397.155,299.1528128,AUTHORITY["EPSG","7004"]],TOWGS84[570.8,85.7,462.8,4.998,1.587,5.261,3.56],AUTHORITY["EPSG","6156"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4156"]],PROJECTION["Krovak"],PARAMETER["latitude_of_center",49.5],PARAMETER["longitude_of_center",24.83333333333333],PARAMETER["azimuth",30.28813972222222],PARAMETER["pseudo_standard_parallel_1",78.5],PARAMETER["scale_factor",0.9999],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],AUTHORITY["EPSG","5514"]]')"""
            cursor.execute(stmt)
            self._conn.commit()
            VfrLogger.msg("EPSG 5514 defined in DB", header=True)

        cursor.close()

    def create_indices(self):
        """Create indices for output tables (gml_id).
        """
        if not self._conn:
            return

        if not self.schema_list:
            self.schema_list = ['public']

        if not self._layer_list:
            for idx in range(self._ods.GetLayerCount()):
                self._layer_list.append(self._ods.GetLayer(idx).GetName())
        
        column = "gml_id"

        cursor = self._conn.cursor()
        for schema in self.schema_list:
            for layer in self._layer_list:
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
                    VfrLogger.warning("Unable to create index %s_%s: %s" % (table, column, e))
                    cursor.execute('ROLLBACK')

        cursor.close()

    def _update_fid_seq(self, table, fid, column = 'ogc_fid'):
        """Update fid sequence.

        @param table: name of table
        @param fid: feature id (max)
        @param column: name of column
        """
        if not self._conn:
            VfrLogger.warning("Unable to update FID sequence for table '%s'" % table)
            return

        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT setval('%s_%s_seq', %d)" % (table, column, fid))
        except StandardError as e:
            VfrLogger.warning("Unable to update FID sequence for table '%s': %s" % (table, e))

        cursor.close()

    def _get_fid_max(self, table, column='ogc_fid'):
        """Get maximal feature id.

        @param table: name of table
        @param column: name of column (key)

        @return max fid or -1 on error
        """
        if not self._conn:
            VfrLogger.warning("No DB connection defined." % table)
            return

        cursor = self._conn.cursor()
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

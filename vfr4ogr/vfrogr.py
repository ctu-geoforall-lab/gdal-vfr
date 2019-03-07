###############################################################################
#
# VFR importer based on GDAL library
#
# Author: Martin Landa <landa.martin gmail.com>
#
# Licence: MIT/X
#
###############################################################################

import os
import sys
import mimetypes
import time
import datetime
import copy
import logging
import re
try:
    # Python 2
    from urllib2 import urlopen, HTTPError
except ImportError:
    # Python 3
    from urllib.request import urlopen, HTTPError
import getpass
from time import gmtime, strftime

try:
    from osgeo import gdal, ogr
except ImportError as e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from .exception import VfrError
from .logger import VfrLogger
from .utils import last_day_of_month, yesterday, parse_xml, extension

class Mode:
    """File open mode.
    """
    write  = 0
    append = 1
    change = 2

class Action:
    """Feature action (changes only).
    """
    add    = 0
    update = 1
    delete = 2

class VfrOgr:
    def __init__(self, frmt, dsn, geom_name=None, layers=[], nogeomskip=False,
                 overwrite=False, lco_options=[]):
        """Class for importing VFK data into selected format using GDAL library.

        Raise VfrError on error.
        
        @param frmt: output format
        @param dsn: output datasource name
        @param geom_name: preferred geometry column name (None for all columns)
        @param layers: list of selected layes ([] for all layers)
        @param nogeomskip: True to skip features without geometry
        @param overwrite: True to overwrite existing files
        @param lco_options: list of layer creation options (see GDAL library for details
        """
        # check for required GDAL version
        self._check_ogr()

        # read configuration
        self._conf = self._read_conf()

        # set up logging
        if self._conf['LOG_DIR']:
            if 'LOG_FILE' in self._conf:
                self._logFile = self._conf['LOG_FILE']
            else:
                if not hasattr(self, '_logFile'):
                    if dsn:
                        self._logFile = 'vfr2ogr-{}'.format(
                            os.path.basename(dsn) if os.path.isabs(dsn) else dsn
                        )
                    else:
                        self._logFile = 'vfr2ogr'

            self._logFile = os.path.join(self._conf['LOG_DIR'], self._logFile)
            if not self._logFile.endswith('.log'):
                self._logFile += '.log'
            VfrLogger.addHandler(logging.FileHandler(self._logFile, delay = True))
            VfrLogger.debug("log: {}".format(self._logFile))
        
        self.frmt = frmt
        self._geom_name = geom_name
        self._overwrite = overwrite
        self._layer_list = layers
        self._nogeomskip = nogeomskip
        self._lco_options = lco_options
        
        self._file_list = []
        
        # input datasource
        self._idrv = ogr.GetDriverByName("GML")
        if self._idrv is None:
            raise VfrError("Unable to select GML driver")
        self._ids = None
        
        # check output datasource
        self.odsn = dsn
        if not self.odsn:
            self._odrv = self._ods = None
            return

        # open driver for output format
        self._odrv = ogr.GetDriverByName(frmt)
        if self._odrv is None:
            raise VfrError("Format '%s' is not supported" % frmt)
        
        # try to open output datasource
        self._ods = self._odrv.Open(self.odsn, True)
        if self._ods is None:
            # if fails, try to create new datasource
            self._ods = self._odrv.CreateDataSource(self.odsn)
        if self._ods is None:
            raise VfrError("Unable to open or create new datasource '%s'" % self.odsn)
        # check also capability to create geometry columns
        try:
            self._create_geom = self._ods.TestCapability(ogr.ODsCCreateGeomFieldAfterCreateLayer)
        except AttributeError:
            self._create_geom = False
        if not self._geom_name and \
           not self._create_geom:
            VfrLogger.warning("Driver '%s' doesn't support multiple geometry columns. "
                              "Only first will be used." % self._odrv.GetName())

        if self._overwrite:
            # overwrite is not support by Esri Shapefile
            if self.frmt != 'Esri Shapefile':
                self._lco_options.append("OVERWRITE=YES")
        if self.frmt == 'Esri Shapefile':
            self._lco_options.append("ENCODING=UTF-8")

    def __del__(self):
        if self._ods:
            # close output datasource
            self._ods.Destroy()

    def _check_ogr(self):
        """Check GDAL/OGR library, version >= 1.11 required.

        Raise VfrError when condition is not satisfied.
        """
        version = gdal.__version__.split('.', 1)
        if not (int(version[0]) > 1 or int(version[1].split('.', 1)[0]) >= 11):
            raise VfrError("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
        
        # check if OGR comes with GML driver
        if not ogr.GetDriverByName('GML'):
            raise VfrError('GML driver required')
        
        gdal.PushErrorHandler(self._error_handler)

    def _error_handler(self, err_level, err_no, err_msg):
        """Redirect warnings produced by GDAL library to the file.

        @param err_level: error level to be redirected
        @param err_no: unused 
        @param error_msg: message
        """
        if err_level > gdal.CE_Warning:
            raise RuntimeError(err_msg)
        elif err_level == gdal.CE_Debug:
            VfrLogger.debug(err_msg + os.linesep)
        else:
            VfrLogger.warning(err_msg)

    def _read_conf(self):
        """Read configuration from file.

        Raise VfrError on failure
        """
        cfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'vfr4ogr.conf')
        if not os.path.isfile(cfile):
            VfrError("Configuration file not found")

        # set default values
        conf = { 'LOG_DIR' : '.',
                 'DATA_DIR' : 'data' }

        # read configuration from file
        with open(cfile) as f:
            for line in f.readlines():
                line = line.strip()
                if line.startswith('#'):
                    continue
                try:
                    key, value = line.split('=')
                except ValueError as e:
                    VfrError("Invalid configuration file on line: {}".format(line))

                conf[key] = value

        # check also environmental variables
        if 'LOG_FILE' in os.environ:
            conf['LOG_FILE'] = os.environ['LOG_FILE']
        if 'DATA_DIR' in os.environ:
            conf['DATA_DIR'] = os.environ['DATA_DIR']
        if 'LOG_DIR' in os.environ:
            conf['LOG_DIR'] = os.environ['LOG_DIR']
        
        # create data directory if not exists
        if not os.path.isabs(conf['DATA_DIR']):
            # convert path to absolute
            conf['DATA_DIR'] = os.path.abspath(conf['DATA_DIR'])
        
        if not os.path.exists(conf['DATA_DIR']):
            os.makedirs(conf['DATA_DIR'])
            VfrLogger.debug("Creating <{}>".format(conf['DATA_DIR']))
        
        return conf

    def _download_vfr(self, url):
        """Downloading VFR file to selected directory.

        Raise VfrError on error.

        @param url: URL where file can be downloaded
        """
        def download_file(self, url, local_file):
            success = True
            with open(local_file, 'wb') as fd:
                try:
                    fd.write(urlopen(url).read())
                except HTTPError as e:
                    if e.code == 404:
                        success = False

            if not success:
                os.remove(local_file)
                raise VfrError("File '%s' not found" % url)
            
        if os.path.exists(url): # single VFR file
            return url

        local_file = os.path.join(self._conf['DATA_DIR'], os.path.basename(url))
        VfrLogger.debug('download_vfr(): local_file={}'.format(local_file))
        if os.path.exists(local_file): # don't download file if found
            return local_file

        VfrLogger.msg("Downloading {} ({})...".format(url, self._conf['DATA_DIR']),
                      header=True)

        if not url.startswith('http://'):
            url = 'http://vdp.cuzk.cz/vymenny_format/soucasna/' + url

        # try more dates when downloading ST_U data (CUZK is
        # publishing data last day in the month, but there can be
        # exceptions due to technical reasons)
        ndays = 0 if 'ST_Z' in url else 3
        old_date = last_day_of_month(string=False)
        for day in range(1, ndays+2):
            try:
                download_file(self, url, local_file)
            except VfrError as e:
                new_date = old_date + datetime.timedelta(days=1)
                url = url.replace(
                    old_date.strftime("%Y%m%d"), new_date.strftime("%Y%m%d")
                )
                local_file = local_file.replace(
                    old_date.strftime("%Y%m%d"), new_date.strftime("%Y%m%d")
                )
                if day < ndays:
                    VfrLogger.error('{}'.format(e))
                    VfrLogger.info("New attempt: '{}'...{}".format(url, os.linesep))
                else:
                    raise VfrError('{}'.format(e))

        return local_file

    def cmd_log(self, cmd):
        """Return cmd log file

        @return string
        """
        VfrLogger.msg('cmd={}\npid={}\nuser={}\ndate={}\ncwd={}\ndata={}\nlog={}'.format(' '.join(sys.argv),
                                                                                         os.getpid(),
                                                                                         getpass.getuser(),
                                                                                         strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                                                                                         os.getcwd(), self._conf['DATA_DIR'], self._logFile),
                      header=True, style='#')

    def reset(self):
        """Reset file list"""
        self._file_list = []

    def download(self, file_list, force_date=None):
        """Download VFR files.

        @param file_list: file list to be processed
        @param force_date: force date if not defined
        
        @return list of VFR files
        """
        VfrLogger.msg("%d VFR file(s) will be processed..." % len(file_list), header=True)
        
        base_url = "http://vdp.cuzk.cz/vymenny_format/"
        for line in file_list:
            if not os.path.isabs(line):
                file_path = os.path.abspath(os.path.join(self._conf['DATA_DIR'], line))
            else:
                file_path = line
            if os.path.exists(file_path):
                ftype, fencoding =  mimetypes.guess_type(file_path)
                if ((ftype in ('application/xml', 'text/xml') and fencoding == 'gzip') or \
                    (ftype in ('application/zip', 'application/x-zip-compressed') and fencoding is None)):
                    # downloaded VFR file, skip
                    self._file_list.append(file_path)
                else:
                    VfrLogger.warning("File <{}>: unsupported minetype '{}'".format(line, ftype))
            else:
                if not line.startswith('http://') and \
                        not line.startswith('20'):
                    # determine date if missing
                    if not force_date:
                        if line.startswith('ST_Z'):
                            date = yesterday()
                        else:
                            date = last_day_of_month()
                    else:
                        date = force_date
                    line = date + '_' + line
                else:
                    reg = re.match('(.*)(\d{8})_(.*)', line)
                    if not reg:
                        raise VfrError("Unable to determine date")
                    date = datetime.datetime.date(
                        datetime.datetime.strptime(reg.group(2), "%Y%m%d")
                    )

                if not line.startswith('http'):
                    # add base url if missing
                    base_url_line = base_url
                    if 'ST_UVOH' not in line:
                        base_url_line += "soucasna/"
                    else:
                        base_url_line += "specialni/"

                    line = base_url_line + line


                ext = '.xml.{}'.format(extension())
                if not line.endswith(ext):
                    # add extension if missing
                    line += ext

                self._file_list.append(self._download_vfr(line))
               
    def print_summary(self):
        """Print summary for multiple file input.
        """
        if self._ods is None:
            return
        stime = time.time()
        layer_list = copy.deepcopy(self._layer_list)
        if not layer_list:
            for idx in range(self._ods.GetLayerCount()):
                layer_list.append(self._ods.GetLayer(idx).GetName())
        
        VfrLogger.msg("Summary", header=True)
        for layer_name in layer_list:
            layer = self._ods.GetLayerByName(layer_name)
            if not layer:
                continue

            VfrLogger.msg("Layer            %-20s ... %10d features\n" % \
                             (layer_name, layer.GetFeatureCount()))
        
        nsec = time.time() - stime    
        etime = str(datetime.timedelta(seconds=nsec))
        VfrLogger.msg("Time elapsed: %s" % str(etime), header=True)

    def _open_ds(self, filename):
        """Open datasource for reading.
        
        Raise VfrError on failure.
        
        @param filename: name of file to be open as datasource

        @return datasource instance
        """
        vsi = '/vsizip/' if extension() == 'zip' else '/vsigzip/'
        self._ids = self._idrv.Open(vsi + filename, False)
        if self._ids is None:
            raise VfrError("Unable to open file '%s'. Skipping.\n" % filename)

        return self._ids
    
    def _list_layers(self, extended = False, fd = sys.stdout):
        """List OGR layers of input VFR file.

        @param extended: True for extended output
        @param fd: file description for output

        @return list of layers
        """
        nlayers = self._ids.GetLayerCount()
        layer_list = list()
        for i in range(nlayers):
            layer = self._ids.GetLayer(i)
            layerName = layer.GetName()
            layer_list.append(layerName)

            if not fd:
                continue

            if extended:
                fd.write('-' * 80 + os.linesep)
            featureCount = layer.GetFeatureCount()
            fd.write("Number of features in %-20s: %d\n" % (layerName, featureCount))
            if extended:
                for field, count in self._get_geom_count(layer):
                    fd.write("%41s : %d\n" % (field, count))

        if fd:
            fd.write('-' * 80 + os.linesep)

        return layer_list

    def _convert_vfr(self, mode = Mode.write, schema=None):
        """Write features from input (VFR) datasource to output datasource

        @param: file mode (see class Mode for details
        @param schema: name of DB schema (relevant only for PG output datasource

        @return number of converted features
        """
        if self._overwrite and mode == Mode.write:
            # delete also layers which are not part of ST_UKSH (do it better?)
            for layer in ("ulice", "parcely", "stavebniobjekty", "adresnimista"):
                if self._ods.GetLayerByName(layer) is not None:
                    self._ods.DeleteLayer(layer)
        
        # process features marked for deletion first
        dlist = None # statistics
        if mode == Mode.change:
            dlayer = self._ids.GetLayerByName('ZaniklePrvky')
            if dlayer:
                dlist = self._process_deleted_features(dlayer)
        
        # process layers
        start = time.time()
        nlayers = self._ids.GetLayerCount()
        nfeat = 0
        for iLayer in range(nlayers):
            layer = self._ids.GetLayer(iLayer)
            layer_name = layer.GetName()
            # force lower case for output layers, some drivers are
            # doing that automatically anyway
            layer_name_lower = layer_name.lower()

            if self._layer_list and layer_name not in self._layer_list:
                # process only selected layers
                continue

            if layer_name == 'ZaniklePrvky':
                # skip deleted features (already done)
                continue

            olayer = self._ods.GetLayerByName('%s' % layer_name_lower)
            VfrLogger.msg("Processing layer %-20s ..." % layer_name)
            if not self._overwrite and (olayer and mode == Mode.write):
                VfrLogger.msg(" already exists (use --overwrite or --append to modify existing data)\n")
                continue

            # fix output drivers not to use default geometry names
            if self.frmt in ('PostgreSQL', 'OCI') and not self._geom_name:
                self._remove_option('GEOMETRY_NAME')
                if layer_name_lower == 'ulice':
                    geom_name = 'definicnicara'
                elif layer_name_lower == 'adresnimista':
                    geom_name = 'adresnibod'
                else:
                    geom_name = 'definicnibod'

                self._lco_options.append('GEOMETRY_NAME={}'.format(geom_name))

            # try to be clever if geometry column specified
            geom_name = self._geom_name
            if self._geom_name and self._geom_name.endswith('Hranice'):
                feat_defn = layer.GetLayerDefn()
                if 0 > feat_defn.GetGeomFieldIndex(self._geom_name):
                    if self._geom_name.startswith('GeneralizovaneHranice'):
                        geom_name = 'OriginalniHranice'
                    else:
                        geom_name = 'GeneralizovaneHranice'
                    if 0 > feat_defn.GetGeomFieldIndex(geom_name):
                        geom_name = 'DefinicniBod'
                        if 0 > feat_defn.GetGeomFieldIndex(geom_name):
                            geom_name = 'DefinicniCara'
                            if 0 > feat_defn.GetGeomFieldIndex(geom_name):
                                geom_name = 'AdresniBod'
                                if 0 > feat_defn.GetGeomFieldIndex(geom_name):
                                    geom_name = None

            # delete layer if exists and append is not True
            if olayer and mode == Mode.write:
                if self._delete_layer(layer_name_lower):
                    olayer = None

            # create new output layer if not exists
            if not olayer:
                olayer = self._create_layer(layer_name_lower, layer, geom_name)
            if olayer is None:
                raise VfrError("Unable to export layer '%s'. Exiting..." % layer_name)

            # pre-process changes
            if mode == Mode.change:
                change_list = self._process_changes(layer, olayer)
                if dlist and layer_name in dlist: # add features to be deleted
                    change_list.update(dlist[layer_name])

            ifeat = n_nogeom = 0
            geom_idx = -1

            # make sure that PG sequence is up-to-date (import for fid == -1)
            fid = -1
            if hasattr(self, "_conn"): # do it better?
                if schema:
                    table_name = '%s.%s' % (schema, layer_name_lower)
                else:
                    table_name = layer_name_lower
                fid = self._get_fid_max(table_name)
                if fid > 0:
                    self._update_fid_seq(table_name, fid)
            
            if fid is None or fid == -1:
                fid = olayer.GetFeatureCount()

            # start transaction in output layer
            if olayer.TestCapability(ogr.OLCTransactions):
                olayer.StartTransaction()

            # delete marked features first (changes only)
            if mode == Mode.change and dlist and layer_name in dlist:
                for fid in dlist[layer_name].keys():
                    olayer.DeleteFeature(fid)

            # do mapping for fields (needed for Esri Shapefile when
            # field names are truncated)
            field_map = [i for i in range(0, layer.GetLayerDefn().GetFieldCount())]

            # copy features from source to destination layer
            layer.ResetReading()
            feature = layer.GetNextFeature()
            while feature:
                # check for changes first (delete/update/add)
                if mode == Mode.change:
                    c_fid = feature.GetFID()
                    action, o_fid = change_list.get(c_fid, (None, None))
                    if action is None:
                        raise VfrError("Layer %s: unable to find feature %d" % (layer_name, c_fid))

                    # feature marked to be changed (delete first)
                    if action in (Action.delete, Action.update):
                        olayer.DeleteFeature(o_fid)

                    # determine fid for new feature
                    if action == Action.add:
                        fid = -1
                    else:
                        fid = o_fid

                    if action == Action.delete:
                        # do nothing and continue
                        feature = layer.GetNextFeature()
                        ifeat += 1
                        continue
                else:
                    fid += 1

                # clone feature
                ofeature = ogr.Feature(olayer.GetLayerDefn())
                ofeature.SetFromWithMap(feature, True, field_map)

                # modify geometry columns if requested
                if geom_name:
                    if geom_idx < 0:
                        geom_idx = feature.GetGeomFieldIndex(geom_name)

                    self._modify_feature(feature, geom_idx, ofeature)

                if ofeature.GetGeometryRef() is None:
                    n_nogeom += 1
                    if self._nogeomskip:
                        # skip feature without geometry
                        feature = layer.GetNextFeature()
                        ofeature.Destroy()
                        continue

                # set feature id
                if fid >= -1:
                    # fid == -1 -> unknown fid
                    ofeature.SetFID(fid)

                # add new feature to output layer
                olayer.CreateFeature(ofeature)

                feature = layer.GetNextFeature()
                ifeat += 1

            # commit transaction in output layer
            if olayer.TestCapability(ogr.OLCTransactions):
                olayer.CommitTransaction()

            # print statistics per layer to the stdout
            VfrLogger.msg(" %10d features" % ifeat)
            if mode == Mode.change:
                n_added = n_updated = n_deleted = 0
                for action, unused in change_list.itervalues():
                    if action == Action.update:
                        n_updated += 1
                    elif action == Action.add:
                        n_added += 1
                    else: # Action.delete:
                        n_deleted += 1
                VfrLogger.msg(" (%5d added, %5d updated, %5d deleted)" % \
                                     (n_added, n_updated, n_deleted))
            else:
                VfrLogger.msg(" added")
                if n_nogeom > 0:
                    if self._nogeomskip:
                        VfrLogger.msg(" (%d without geometry skipped)" % n_nogeom)
                    else:
                        VfrLogger.msg(" (%d without geometry)" % n_nogeom)
            VfrLogger.msg("\n")

            nfeat += ifeat

            # update sequence for PG
            if hasattr(self, "_conn"):
                if fid > 0:
                    if schema:
                        table_name = '%s.%s' % (schema, layer_name_lower)
                    else:
                        table_name = layer_name_lower
                    self._update_fid_seq(table_name, fid)
        
        # final statistics (time elapsed)
        VfrLogger.msg("Time elapsed: %d sec" % (time.time() - start), header=True)

        return nfeat

    def _remove_option(self, name):
        """Remove specified option from list

        @param name: option to be removed
        """
        i = 0
        for opt in self._lco_options:
            if opt.startswith(name):
                del self._lco_options[i]
                return 
            i += 1

    def _delete_layer(self, layerName):
        """Delete specified layer from output datasource

        @param layerName: name of layer to be deleted

        @return True if deleted other False
        """
        nlayersOut = self._ods.GetLayerCount()
        for iLayerOut in range(nlayersOut): # do it better
            if self._ods.GetLayer(iLayerOut).GetName() == layerName:
                self._ods.DeleteLayer(iLayerOut)
                return True

        return False

    def _create_layer(self, layerName, ilayer, force_geom_name=None):
        """Create new layer in output datasource.

        @param layerName: name of layer to be created
        @param ilayer: layer instance (input datasource)

        @return layer instance (output datasource)
        """
        ofrmt = self._ods.GetDriver().GetName()
        # determine geometry type
        geom_name = force_geom_name if force_geom_name else self._geom_name
        if geom_name or not self._create_geom:
            feat_defn = ilayer.GetLayerDefn()
            if geom_name:
                idx = feat_defn.GetGeomFieldIndex(geom_name)
            else:
                idx = 0

            if idx > -1:
                geom_type = feat_defn.GetGeomFieldDefn(idx).GetType()
            else:
                geom_type = ilayer.GetGeomType()
                idx = 0

            if ofrmt in ('PostgreSQL', 'OCI'):
                self._remove_option('GEOMETRY_NAME')
                self._lco_options.append('GEOMETRY_NAME=%s' % feat_defn.GetGeomFieldDefn(idx).GetName().lower())
        else:
            geom_type = ogr.wkbNone

        # create new layer
        olayer = self._ods.CreateLayer(layerName, ilayer.GetSpatialRef(),
                                       geom_type, self._lco_options)

        if not olayer:
            raise VfrError("Unable to create layer '%'" % layerName)

        # create attributes                     
        feat_defn = ilayer.GetLayerDefn()
        for i in range(feat_defn.GetFieldCount()):
            ifield = feat_defn.GetFieldDefn(i)
            ofield = ogr.FieldDefn(ifield.GetNameRef(), ifield.GetType())
            ofield.SetWidth(ifield.GetWidth())
            if ofrmt == 'ESRI Shapefile':
                # StringList not supported by Esri Shapefile
                types = [ogr.OFTIntegerList, ogr.OFTRealList, ogr.OFTStringList]
                if gdal.__version__.split('.')[0] == '2':
                    types.append(ogr.OFTInteger64List)
                if ifield.GetType() in types:
                    ofield.SetType(ogr.OFTString)

            olayer.CreateField(ofield)

        # create also geometry attributes
        if not geom_name and \
                olayer.TestCapability(ogr.OLCCreateGeomField):
            for i in range(feat_defn.GetGeomFieldCount()):
                geom_defn = feat_defn.GetGeomFieldDefn(i) 
                if geom_name and \
                   geom_defn.GetName() != geom_name:
                    continue
                olayer.CreateGeomField(feat_defn.GetGeomFieldDefn(i))

        return olayer

    def _get_geom_count(self, layer):
        """Get list of geometry column for specified layer.

        @param: layer instance
        
        @return list of column names
        """
        defn = layer.GetLayerDefn()
        geom_list = list()
        for i in range(defn.GetGeomFieldCount()):
            geom_list.append([defn.GetGeomFieldDefn(i).GetName(), 0])

        for feature in layer:
            for i in range(len(geom_list)):
                if feature.GetGeomFieldRef(i):
                    geom_list[i][1] += 1

        return geom_list

    def _modify_feature(self, feature, geom_idx, ofeature, suppress=True):
        """Modify output feature - remove remaining geometry columns.

        @param feature: input feature
        @param geom_idx: index of geometry column to be kept
        @param ofeature: feature to be modified
        @param suppress: suppress warnings
        """
        # set requested geometry
        if geom_idx > -1:
            geom = feature.GetGeomFieldRef(geom_idx)
            if geom:
                ofeature.SetGeometry(geom.Clone())
            else:
                ofeature.SetGeometry(None)
                if not suppress:
                    VfrLogger.warning("Feature %d has no geometry (geometry column: %d)" % \
                                      (feature.GetFID(), geom_idx))
                    
        return geom_idx

    def _process_changes(self, ilayer, olayer, column='gml_id'):
        """Process list of features (per layer) to be modified (update/add).

        @todo: use numeric data as key

        @param ilayer: input layer instance
        @param olayer: output layer instance
        @param column: key column to be processed
        
        @return directory where keys are fids from input (VFR) layer and
        items are tuples (action, fid of existing feature if found)
        """
        changes_list = {}

        ilayer.ResetReading()
        ifeature = ilayer.GetNextFeature()
        while ifeature:
            fcode = ifeature.GetField(column)
            # check if feature already exists in output layer
            found = []
            olayer.SetAttributeFilter("%s = '%s'" % (column, fcode))
            for feature in olayer:
                found.append(feature.GetFID())

            n_feat = len(found)

            changes_list[ifeature.GetFID()] = (Action.update, found[0]) if n_feat > 0 \
                                              else (Action.add, -1)

            if n_feat > 1:
                # TODO: how to handle correctly?
                VfrLogger.warning("Layer '%s': %d features '%s' found. "
                                  "Duplicated features will be deleted." % \
                            (olayer.GetName(), n_feat, fcode))
                for fid in found[1:]:
                    # delete duplicates
                    olayer.DeleteFeature(fid)

            ifeature = ilayer.GetNextFeature()

        # unset attribute filter
        olayer.SetAttributeFilter(None)

        return changes_list

    def _process_deleted_features(self, layer):
        """Process deleted features (process OGR layer 'ZaniklePrvky')

        @param layer: layer instance

        @return: list of deleted features per layer as tuple (action,
        fid)
        """
        lcode2lname = {
            'ST' : 'Staty',
            'RS' : 'RegionySoudrznosti',
            'KR' : 'Kraje',
            'VC' : 'Vusc',
            'OK' : 'Okresy',
            'OP' : 'Orp',
            'PU' : 'Pou',
            'OB' : 'Obce',
            'SP' : 'SpravniObvody',
            'MP' : 'Mop',
            'MC' : 'Momc',
            'CO' : 'CastiObci',
            'KU' : 'KatastralniUzemi',
            'ZJ' : 'Zsj',
            'UL' : 'Ulice',
            'PA' : 'Parcely',
            'SO' : 'StavebniObjekty',
            'AD' : 'AdresniMista',
            }
        column = 'gml_id'
        dlist = {}
        for layer_name in lcode2lname.itervalues():
            dlist[layer_name] = {}

        layer.ResetReading()
        feature = layer.GetNextFeature()
        layer_previous = None
        while feature:
            # determine layer and attribute filter for given feature
            lcode = feature.GetField("TypPrvkuKod")
            layer_name = lcode2lname.get(lcode, None)
            if not layer_name:
                VfrLogger.error("Unknown layer code '{}'".format(lcode))
                feature = layer.GetNextFeature()
                continue
            if self._layer_list and layer_name not in self._layer_list:
                feature = layer.GetNextFeature()
                continue
            fcode = "%s.%s" % (lcode, feature.GetField("PrvekId"))
            if not layer_previous or layer_previous != layer_name:
                dlayer = self._ods.GetLayerByName('%s' % layer_name)
                if dlayer is None:
                    VfrLogger.error("Layer '{}' not found".format(layer_name))
                    feature = layer.GetNextFeature()
                    continue

            # find features to be deleted (collect their FIDs)
            n_feat = 0
            dlayer.SetAttributeFilter("%s = '%s'" % (column, fcode))
            for dfeature in dlayer:
                fid = dfeature.GetFID()
                dlist[layer_name][fid] = (Action.delete, fid)
                n_feat += 1
            dlayer.SetAttributeFilter(None)

            # check for consistency (one feature should be found)
            if n_feat == 0:
                VfrLogger.warning("Layer '%s': no feature '%s' found. "
                                  "Nothing to delete." % \
                            (layer_name, fcode))
            elif n_feat > 1:
                VfrLogger.warning("Layer '%s': %d features '%s' found. "
                                  "All of them will be deleted." % (layer_name, n_feat, fcode))

            layer_previous = layer_name
            feature = layer.GetNextFeature()

        # return statistics
        return dlist

    def run(self, append=False, extended=False):
        """Run conversion process.

        @param append: True for append mode (add features to output)
        @param extended: True for extended statistics

        @return number of passes
        """
        ipass = 0
        stime = time.time()
        layer_list = copy.deepcopy(self._layer_list)
        
        pg = hasattr(self, "_conn") # PG is output datasource
        if pg:
            self.schema_list = []
            epsg_checked = False
        
        for fname in self._file_list:
            VfrLogger.msg("Processing %s (%d out of %d)..." % \
                          (fname, ipass+1, len(self._file_list)), header=True)
            
            # open OGR datasource
            try:
                ids = self._open_ds(fname)
            except VfrError as e:
                VfrLogger.error(str(e))
                continue
            
            if ids is None:
                ipass += 1
                continue # unable to open - skip
            
            if not self.odsn:
                # no output datasource given -> list available layers and exit
                layer_list = self._list_layers(extended, sys.stdout)
                if extended and os.path.exists(filename):
                    compare_list(layer_list, parse_xml(filename))
            else:
                if self.odsn is None:
                    self.odsn = '.' # current directory
                    
                if pg and not epsg_checked:
                    # check if EPSG 5514 exists in output DB (only first pass)
                    self._check_epsg()
                    epsg_checked = True
                    
                if not layer_list:
                    for l in self._list_layers(fd=None):
                        if l not in layer_list:
                            layer_list.append(l)

                schema_name = None                
                if pg:
                    # build datasource string per file
                    odsn_reset = self.odsn
                    if self._schema_per_file or self._schema:
                        if self._schema_per_file:
                            # set schema per file
                            ext = fname.split('.', 1)[1]
                            schema_name = os.path.basename(fname).rstrip('.' + ext).lower()
                            if schema_name[0].isdigit():
                                schema_name = 'vfr_' + schema_name
                        else:
                            schema_name = self._schema.lower()

                        # create schema in output DB if needed
                        self._create_schema(schema_name)
                        self.odsn += ' active_schema=%s' % schema_name
                        if schema_name not in self.schema_list:
                            self.schema_list.append(schema_name)
                        self._ods.Destroy() # TODO: do it better
                        self._ods = self._odrv.Open(self.odsn, True)
                        if self._ods is None:
                            raise VfrError("Unable to open or create new datasource '%s'" % self.odsn)
                
                # check mode - process changes or append
                mode = Mode.write
                if fname.split('_')[-1][0] == 'Z':
                    mode = Mode.change
                    if pg:
                        # insert required
                        os.environ['PG_USE_COPY'] = 'NO'
                elif append:
                    mode = Mode.append
                    if pg:
                        # force copy over insert
                        os.environ['PG_USE_COPY'] = 'YES'
                
                # do the conversion
                try:
                    nfeat = self._convert_vfr(mode, schema_name)
                except RuntimeError as e:
                    raise VfrError("Unable to read %s: %s" % (fname, e))
                
                if pg:
                    # reset datasource string per file
                    if self._schema_per_file or self._schema:
                        self.odsn = odsn_reset
                        self._ods.Destroy()
                        self._ods = self._odrv.Open(self.odsn, True)
                        if self._ods is None:
                            raise VfrError("Unable to open or create new datasource '%s'" % self.odsn)
                
                if nfeat > 0:
                    append = True # append on next passes

            ids.Destroy()
            self._ids = None
            ipass += 1
        
        return ipass

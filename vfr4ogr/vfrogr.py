import os
import sys
import mimetypes
import time
import datetime
import copy

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from exception import VfrError
from logger import VfrLogger

# file mode
class Mode:
    write  = 0
    append = 1
    change = 2

# feature action (changes only)
class Action:
    add    = 0
    update = 1
    delete = 2

class VfrOgr:
    def __init__(self, frmt, dsn, geom_name=None, layers=[], nogeomskip=False,
                 overwrite=False, lco_options=[]):
        self._check_ogr()
        
        self.frmt = frmt
        self._geom_name = geom_name
        self._overwrite = overwrite
        self._layer_list = layers
        self._nogeomskip = nogeomskip
        self._lco_options = lco_options
        
        self._file_list = []
        
        # input
        self._idrv = ogr.GetDriverByName("GML")
        if self._idrv is None:
            raise VfrError("Unable to select GML driver")
        self._ids = None
        
        # output
        self.odsn = dsn
        if not self.odsn:
            self._odrv = self._ods = None
            return

        self._odrv = ogr.GetDriverByName(frmt)
        if self._odrv is None:
            raise VfrError("Format '%s' is not supported" % frmt)
        
        # try to open datasource
        self._ods = self._odrv.Open(self.odsn, True)
        if self._ods is None:
            # if fails, try to create new datasource
            self._ods = self._odrv.CreateDataSource(self.odsn)
        if self._ods is None:
            raise VfrError("Unable to open or create new datasource '%s'" % self.odsn)
        self._create_geom = self._ods.TestCapability(ogr.ODsCCreateGeomFieldAfterCreateLayer)
        if not self._geom_name and \
           not self._create_geom:
            VfrLogger.warning("Driver '%s' doesn't support multiple geometry columns. "
                              "Only first will be used." % self._odrv.GetName())

        # OVERWRITE is not support by Esri Shapefile
        if self._overwrite:
            if self.frmt != 'ESRI Shapefile':
                self._lco_options.append("OVERWRITE=YES")

    def __del__(self):
        if self._ods:
            # close output datasource
            self._ods.Destroy()

    def _check_ogr(self):
        # check GDAL/OGR library, version >= 1.11 required
        version = gdal.__version__.split('.', 1)
        if not (int(version[0]) > 1 or int(version[1].split('.', 1)[0]) >= 11):
            raise VfrError("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
        
        # check if OGR comes with GML driver
        if not ogr.GetDriverByName('GML'):
            raise VfrError('GML driver required')
        
        gdal.PushErrorHandler(self._error_handler)

    # redirect warnings to the file
    def _error_handler(self,err_level, err_no, err_msg):
        if err_level > gdal.CE_Warning:
            raise RuntimeError(err_msg)
        elif err_level == gdal.CE_Debug:
            VfrLogger.debug(err_msg + os.linesep)
        else:
            VfrLogger.warning(err_msg)

    def open_file(self, filename, force_date = None):
        self._file_list = list()
        ds = None
        if os.linesep in filename:
            # already list of files (date range)
            return filename.split(os.linesep)

        mtype = mimetypes.guess_type(filename)[0]
        if mtype is None or 'xml' not in mtype:
            # assuming text file containing list of VFR files
            try:
                f = open(filename)
                i = 0
                lines = f.read().splitlines()
                for line in lines:
                    if len(line) < 1 or line.startswith('#'):
                        continue # skip empty or commented lines 

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

                    if not line.endswith('.xml.gz'):
                        # add extension if missing
                        line += '.xml.gz'

                    if not os.path.exists(line):
                        if not line.startswith('http://'):
                            line = 'http://vdp.cuzk.cz/vymenny_format/soucasna/' + line
                        line = download_vfr(line)

                    self._file_list.append(line)
                    i += 1
                VfrLogger.msg("%d VFR files will be processed..." % len(self._file_list))
            except IOError:
                raise VfrError("Unable to read '%s'" % filename)
            f.close()    
        else:
            # single VFR file
            self._file_list.append(filename)

        return self._file_list

    # print summary for multiple file input
    def print_summary(self):
        stime = time.time()
        layer_list = copy.deepcopy(self._layer_list)
        if not layer_list:
            for idx in range(self._ods.GetLayerCount()):
                layer_list.append(self._ods.GetLayer(idx).GetName())
        
        VfrLogger.msg("Summary")
        for layer_name in layer_list:
            layer = self._ods.GetLayerByName(layer_name)
            if not layer:
                continue

            sys.stdout.write("Layer            %-20s ... %10d features\n" % \
                             (layer_name, layer.GetFeatureCount()))
        
        nsec = time.time() - stime    
        etime = str(datetime.timedelta(seconds=nsec))
        VfrLogger.msg("Time elapsed: %s" % str(etime))

    # open OGR data-source for reading
    def _open_ds(self, filename):
        self._ids = self._idrv.Open(filename, False)
        if self._ids is None:
            raise VfrError("Unable to open file '%s'. Skipping.\n" % filename)

        return self._ids
    
    # list OGR layers of input VFR file
    def _list_layers(self, extended = False, fd = sys.stdout):
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

    # write VFR features to output data-source
    def _convert_vfr(self, mode = Mode.write, schema=None):
        if self._overwrite and mode == Mode.write:
            # delete also layers which are not part of ST_UKSH
            for layer in ("ulice", "parcely", "stavebniobjekty", "adresnimista"):
                if self._ods.GetLayerByName(layer) is not None:
                    self._ods.DeleteLayer(layer)
        
        # process features marked for deletion first
        dlist = None # statistics
        if mode == Mode.change:
            dlayer = ids.GetLayerByName('ZaniklePrvky')
            if dlayer:
                dlist = self._process_deleted_features(dlayer)
        
        # process layers
        start = time.time()
        nlayers = self._ids.GetLayerCount()
        nfeat = 0
        for iLayer in range(nlayers):
            layer = self._ids.GetLayer(iLayer)
            layer_name = layer.GetName()
            ### force lower case for output layers, some drivers are doing
            ### that automatically anyway
            layer_name_lower = layer_name.lower()

            if self._layer_list and layer_name not in self._layer_list:
                # process only selected layers
                continue

            if layer_name == 'ZaniklePrvky':
                # skip deleted features (already done)
                continue

            olayer = self._ods.GetLayerByName('%s' % layer_name_lower)
            sys.stdout.write("Processing layer %-20s ..." % layer_name)
            if not self._overwrite and (olayer and mode == Mode.write):
                sys.stdout.write(" already exists (use --overwrite or --append to modify existing data)\n")
                continue

            ### TODO: fix output drivers not to use default geometry
            ### names
            if self.frmt in ('PostgreSQL', 'OCI') and not self._geom_name:
                if layer_name_lower == 'ulice':
                    self._remove_option('GEOMETRY_NAME')
                    self._lco_options.append('GEOMETRY_NAME=definicnicara')
                else:
                    self._remove_option('GEOMETRY_NAME')
                    self._lco_options.append('GEOMETRY_NAME=definicnibod')

            # delete layer if exists and append is not True
            if olayer and mode == Mode.write:
                if self._delete_layer(layer_name_lower):
                    olayer = None

            # create new output layer if not exists
            if not olayer:
                olayer = self._create_layer(layer_name_lower, layer)
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
            if hasattr(self, "_conn"): # TODO (do it better)
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
                ### ofeature = feature.Clone() # replace by SetFrom()
                ofeature = ogr.Feature(olayer.GetLayerDefn())
                ofeature.SetFromWithMap(feature, True, field_map)

                # modify geometry columns if requested
                if self._geom_name:
                    if geom_idx < 0:
                        geom_idx = feature.GetGeomFieldIndex(self._geom_name)

                        # delete remaining geometry columns
                        ### not needed - see SetFrom()
                        ### odefn = ofeature.GetDefnRef()
                        ### for i in range(odefn.GetGeomFieldCount()):
                        ###    if i == geom_idx:
                        ###        continue
                        ###    odefn.DeleteGeomFieldDefn(i)

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

            # print statistics per layer
            sys.stdout.write(" %10d features" % ifeat)
            if mode == Mode.change:
                n_added = n_updated = n_deleted = 0
                for action, unused in change_list.itervalues():
                    if action == Action.update:
                        n_updated += 1
                    elif action == Action.add:
                        n_added += 1
                    else: # Action.delete:
                        n_deleted += 1
                sys.stdout.write(" (%5d added, %5d updated, %5d deleted)" % \
                                     (n_added, n_updated, n_deleted))
            else:
                sys.stdout.write(" added")
                if n_nogeom > 0:
                    if self._nogeomskip:
                        sys.stdout.write(" (%d without geometry skipped)" % n_nogeom)
                    else:
                        sys.stdout.write(" (%d without geometry)" % n_nogeom)
            sys.stdout.write("\n")

            nfeat += ifeat

            # update sequence for PG
            if hasattr(self, "_conn"):
                ### fid = get_fid_max(userdata['pgconn'], layer_name_lower)
                if fid > 0:
                    if schema:
                        table_name = '%s.%s' % (schema, layer_name_lower)
                    else:
                        table_name = layer_name_lower
                    self._update_fid_seq(table_name, fid)
        
        # final statistics (time elapsed)
        VfrLogger.msg("Time elapsed: %d sec" % (time.time() - start))

        return nfeat

    # remove specified option from list
    def _remove_option(self, name):
        i = 0
        for opt in self._lco_options:
            if opt.startswith(name):
                del self._lco_options[i]
                return 
            i += 1

    # delete specified layer from output data-source
    def _delete_layer(self, layerName):
        nlayersOut = self._ods.GetLayerCount()
        for iLayerOut in range(nlayersOut): # do it better
            if self._ods.GetLayer(iLayerOut).GetName() == layerName:
                self._ods.DeleteLayer(iLayerOut)
                return True

        return False

    # create new layer in output data-source
    def _create_layer(self, layerName, ilayer):
        ofrmt = self._ods.GetDriver().GetName()
        # determine geometry type
        if self._geom_name or not self._create_geom:
            feat_defn = ilayer.GetLayerDefn()
            if self._geom_name:
                idx = feat_defn.GetGeomFieldIndex(self._geom_name)
            else:
                idx = 0

            if idx > -1:
                geom_type = feat_defn.GetGeomFieldDefn(idx).GetType()
            else:
                # warning("Layer '%s': geometry '%s' not available" % (layerName, geom_name))
                geom_type = ilayer.GetGeomType()
                idx = 0

            if ofrmt in ('PostgreSQL', 'OCI'):
                remove_option(options, 'GEOMETRY_NAME')
                options.append('GEOMETRY_NAME=%s' % feat_defn.GetGeomFieldDefn(idx).GetName().lower())
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
        if not self._geom_name and \
                olayer.TestCapability(ogr.OLCCreateGeomField):
            for i in range(feat_defn.GetGeomFieldCount()):
                geom_defn = feat_defn.GetGeomFieldDefn(i) 
                if self._geom_name and \
                   geom_defn.GetName() != self._geom_name:
                    continue
                olayer.CreateGeomField(feat_defn.GetGeomFieldDefn(i))

        return olayer

    # get list of geometry column for specified layer
    def _get_geom_count(self, layer):
        defn = layer.GetLayerDefn()
        geom_list = list()
        for i in range(defn.GetGeomFieldCount()):
            geom_list.append([defn.GetGeomFieldDefn(i).GetName(), 0])

        for feature in layer:
            for i in range(len(geom_list)):
                if feature.GetGeomFieldRef(i):
                    geom_list[i][1] += 1

        return geom_list

    # modify output feature - remove remaining geometry columns
    def _modify_feature(self, feature, geom_idx, ofeature, suppress=False):
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

    # process list of features (per layer) to be modified (update/add)
    #
    # returns directory where keys are fids from input (VFR) layer and
    # items are tuples (action, fid of existing feature if found)
    #
    # TODO: use numeric data as key
    def _process_changes(self, ilayer, olayer, column='gml_id'):
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
                VfrLogger.warning("Layer '%s': %d features '%s' found. Duplicated features will be deleted." % \
                            (olayer.GetName(), n_feat, fcode))
                for fid in found[1:]:
                    # delete duplicates
                    olayer.DeleteFeature(fid)

            ifeature = ilayer.GetNextFeature()

        # unset attribute filter
        olayer.SetAttributeFilter(None)

        return changes_list

    # process deleted features (process OGR layer 'ZaniklePrvky')
    def _process_deleted_features(self, layer):
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
                error("Unknown layer code '%s'" % lcode)
                feature = layer.GetNextFeature()
                continue
            if self._layer_list and layer_name not in self._layer_list:
                feature = layer.GetNextFeature()
                continue
            fcode = "%s.%s" % (lcode, feature.GetField("PrvekId"))
            if not layer_previous or layer_previous != layer_name:
                dlayer = self._ods.GetLayerByName('%s' % layer_name)
                if dlayer is None:
                    error("Layer '%s' not found" % layer_name)
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
        ipass = 0
        stime = time.time()
        layer_list = copy.deepcopy(self._layer_list)
        
        pg = hasattr(self, "_conn")
        if pg:
            self.schema_list = []
            epsg_checked = False
        
        for fname in self._file_list:
            VfrLogger.msg("Processing %s (%d out of %d)..." % \
                          (fname, ipass+1, len(self._file_list)))
            
            # open OGR datasource
            ids = self._open_ds(fname)
            if ids is None:
                ipass += 1
                continue # unable to open - skip
            
            if not self.odsn:
                # no output datasource given -> list available layers and exit
                layer_list = self._list_layers(extended, sys.stdout)
                if extended and os.path.exists(filename):
                    compare_list(layer_list, parse_xml_gz(filename))
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
                
                if pg:
                    # build datasource string per file
                    odsn_reset = self.odsn
                    schema_name = None
                    if self._schema_per_file or self._schema:
                        if self._schema_per_file:
                            # set schema per file
                            schema_name = os.path.basename(fname).rstrip('.xml.gz').lower()
                            if schema_name[0].isdigit():
                                schema_name = 'vfr_' + schema_name
                        else:
                            schema_name = options['schema'].lower()

                        # create schema in output DB if needed
                        self._create_schema(conn, schema_name)
                        odsn += ' active_schema=%s' % schema_name
                        if schema_name not in self.schema_list:
                            self.schema_list.append(schema_name)

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
                    nfeat = self._convert_vfr(mode)
                except RuntimeError as e:
                    raise VfrError("Unable to read %s: %s" % (fname, e))
                
                if pg:
                    # reset datasource string per file
                    if self._schema_per_file:
                        self.odsn = odsn_reset
                
                if nfeat > 0:
                    append = True # append on next passes

            ids.Destroy()
            self._ids = None
            ipass += 1

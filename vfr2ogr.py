#!/usr/bin/env python

"""
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL library version 1.11 or later.

One of input options must be given:
       --file
       --type

Usage: vfr2ogr [-f] [-e] [-d] [--file=/path/to/vfr/filename] [--date=YYYYMMDD] [--type=ST_ABCD|OB_000000_ABCD] [--layer=layer1,layer2,...] [--geom=OriginalniHranice|GeneralizovaneHranice]
                              [--format=<output format>] [--dsn=<OGR datasource>]
                              [--overwrite] [--append]

       -f          List supported output formats
       -e          Extended layer list statistics 
       -d          Download VFR data in currect directory (--type required)
       -g          Skip features without geometry
       --file      Path to xml.gz or URL list file
       --date      Date in format 'YYYYMMDD'
       --type      Type of request in format XY_ABCD, eg. 'ST_UKSH' or 'OB_000000_ABCD'
       --layer     Import only selected layers separated by comma (if not given all layers are processed)
       --geom      Preferred geometry 'OriginalniHranice' or 'GeneralizovaneHranice' (if not found or not given than first geometry is used)
       --format    Output format
       --dsn       Output OGR datasource
       --overwrite Overwrite existing files
       --append    Append to existing files

"""

import os
import sys
import atexit
import time
from getopt import GetoptError

from vfr4ogr.ogr import check_ogr, open_file, list_layers, convert_vfr, open_ds, print_summary
from vfr4ogr.vfr import Mode
from vfr4ogr.utils import fatal, message, parse_xml_gz, compare_list, error, check_log
from vfr4ogr.parse import parse_cmd

# print usage
def usage():
    print __doc__

def main():
    # check requirements
    check_ogr()

    # parse cmd arguments
    options = { 'format' : None, 'dsn' : None, 'overwrite' : False, 'extended' : False,
                'layer' : [], 'geom' : None, 'download' : False, 'append' : False, 'date' : None,
                'nogeomskip': False}
    try:
        filename = parse_cmd(sys.argv, "haofedg", ["help", "overwrite", "extended", "append",
                                                   "file=", "date=", "type=", "layer=", "geom=",
                                                   "format=", "dsn="], options)
    except GetoptError, e:
        usage()
        if str(e):
            fatal(e)
        else:
            sys.exit(0)
   
    lco_options = []
    file_list  = open_file(filename, options['download'], force_date = options['date'])
    if options['download']:
        return 0
    
    # get list of layers
    layer_list = options['layer']
    
    # set up driver-specific options
    if options['format'] == 'SQLite':
        os.environ['OGR_SQLITE_SYNCHRONOUS'] = 'OFF'
    elif options['format'] == 'Esri Shapefile':
        lco_options.append('ENCODING=UTF-8')
    
    append = options['append']
    ipass = 0
    stime = time.time()
    for fname in file_list:
        message("Processing %s (%d out of %d)..." % (fname, ipass+1, len(file_list)))

        # open OGR datasource
        ids = open_ds(fname)
        if ids is None:
            ipass += 1
            continue # unable to open - skip
        
        if options['format'] is None:
            # list available layers and exit
            layer_list = list_layers(ids, options['extended'])
            if options['extended'] and os.path.exists(filename):
                compare_list(layer_list, parse_xml_gz(filename))
        else:
            if options['dsn'] is None:
                fatal("Output datasource not defined")
            
            if not layer_list:
                layer_list = list_layers(ids, False, None)
            
            # check mode - process changes or append
            mode = Mode.write
            if fname.split('_')[-1][0] == 'Z':
                mode = Mode.change
            elif append:
                mode = Mode.append

            # do the conversion
            try:
                nfeat = convert_vfr(ids=ids, odsn=options['dsn'], frmt=options['format'],
                                    layers=options['layer'], overwrite=options['overwrite'],
                                    options=lco_options, geom_name=options['geom'], mode=mode,
                                    nogeomskip=options['nogeomskip'])
            except RuntimeError as e:
                error("Unable to read %s: %s" % (fname, e))
            
            if nfeat > 0:
                append = True # append on next passes

        ids.Destroy()
        ipass += 1
    
    if ipass > 1 or options.get('append', True):
        print_summary(options['dsn'], options['format'], layer_list, stime)
    
    return 0

if __name__ == "__main__":
    atexit.register(check_log)
    sys.exit(main())

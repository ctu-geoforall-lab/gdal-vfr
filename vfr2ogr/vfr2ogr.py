#!/usr/bin/env python

"""
Converts VFR file into desired GIS format supported by OGR library.

Requires GDAL/OGR library version 1.11 or later.

Usage: vfr2ogr.py [-f] /path/to/filename --format=<output format> --dsn=<OGR datasource>

       -f       List supported output formats
       --format Output format
       --dsn    Output OGR datasource
"""

import os
import sys
import getopt

try:
  from osgeo import gdal, ogr
except:
    sys.exit('ERROR: Import of ogr from osgeo failed')

def fatal(msg):
    sys.exit('ERROR: ' + msg)

# print usage
def usage():
    print __doc__

# check GDAL/OGR library, version >= 1.11 required
def check_ogr():
    # check required version
    version = gdal.__version__.split('.', 1)
    if not (int(version[0]) >= 1 and int(version[1][:2]) >= 11):
        fatal("GDAL/OGR 1.11 or later required (%s found)" % '.'.join(version))
    
    # check if OGR comes with GML driver
    if not ogr.GetDriverByName('GML'):
        fatal('GML driver required')

# list formats
def list_formats():
    cnt = ogr.GetDriverCount()
    
    formatsList = [] 
    for i in range(cnt):
        driver = ogr.GetDriver(i)
        if not driver.TestCapability("CreateDataSource"):
            continue
        driverName = driver.GetName()
        if driverName == 'GML':
            continue
        
        formatsList.append(driverName)
    
    for i in sorted(formatsList):
        print i

# convert VFR into specified format
def convert_vfr(vfr, odsn, frm):
    idrv = ogr.GetDriverByName("GML")
    idsn = idrv.Open(vfr, False)
    if idsn is None:
        fatal("Unable to open '%s'" % vfr)

    nlayers = idsn.GetLayerCount()
    for i in range(nlayers):
        layer = idsn.GetLayer(i)
        featureCount = layer.GetFeatureCount()
        print "Number of features in %-20s: %d" % (layer.GetName(), featureCount)

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
    filename = sys.argv[1]
    if filename.startswith('-'):
        fatal('No input file specified')
    if not os.path.isfile(filename):
        usage()
        fatal("'%s' doesn't exists or is not a file" % filename)
    
    # parse options
    try:
        opts, args = getopt.getopt(sys.argv[2:], "hfv", ["help", "format=", "dsn="])
    except getopt.GetoptError as err:
        print str(err) 
        usage()
        sys.exit(2)
    
    oformat = odsn = None
    for o, a in opts:
        if o in ("--v", "--verbose"):
            verbose = True
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
    
    if oformat is None:
        fatal("Output format not defined")

    if odsn is None:
        fatal("Output datasource not defined")
    
    convert_vfr(filename, odsn, oformat)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

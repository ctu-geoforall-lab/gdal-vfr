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
import gzip
import urllib2
import datetime
from xml.dom.minidom import parse, parseString

try:
    from osgeo import gdal, ogr
except ImportError, e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from exception import VfrError
from logger import VfrLogger

def list_formats():
    """List supported OGR formats (write access).
    """
    cnt = ogr.GetDriverCount()
    
    formatsList = [] 
    for i in range(cnt):
        driver = ogr.GetDriver(i)
        if not driver.TestCapability("CreateDataSource"):
            continue
        driverName = driver.GetName()
        if driverName == 'GML':
            continue
        
        formatsList.append(driverName.replace(' ', '_'))
    
    for i in sorted(formatsList):
        print i

def check_file(filename):
    """Check input VFR file exists.

    Raise VfrError on error.
    
    @param: file name
    
    @return file name or None
    """
    if not filename:
        return None
    
    if filename.startswith('-'):
        raise VfrError('No input file specified')
    if not os.path.isfile(filename):
        raise VfrError("'%s' doesn't exists or it's not a file" % filename)
    
    return filename

def parse_xml_gz(filename):
    """Parse VFR (XML) file.

    @param filename: name of VFR file to be parsed

    @return list of items
    """
    VfrLogger.msg("Comparing OGR layers and input XML file (may take some time)...")
    infile = gzip.open(filename)
    content = infile.read()
    
    # parse xml file content
    dom = parseString(content)
    data = dom.getElementsByTagName('vf:Data')[0]
    if data is None:
        raise VfrError("vf:Data not found")

    item_list = []
    for item in data.childNodes:
        item_list.append(item.tagName.lstrip('vf:'))
    
    return item_list

def compare_list(list1, list2):
    """Compare list of XML nodes (see parse_xml_gz()).

    @param list1: first list
    @param list2: second list
    """
    for item in list1:
        if item not in list2:
            print "+ %s" % item
    
    for item in list2:
        if item not in list1:
            print "- %s" % item

def download_vfr(url):
    """Downloading VFR file to current directory.

    Raise VfrError on error.
    
    @param url: URL where file can be downloaded
    """
    VfrLogger.msg("Downloading %s into currect directory..." % url)
    local_file = os.path.basename(url)
    fd = open(local_file, 'wb')
    try:
        fd.write(urllib2.urlopen(url).read())
    except urllib2.HTTPError as e:
        fd.close()
        if e.code == 404:
            os.remove(local_file)
            raise VfrError("File '%s' not found" % url)
        
    fd.close()
    
    return local_file

def last_day_of_month(string = True):
    """Get last day of current month.

    @param string: True to return string otherwise DateTime

    @return date as string or DateTime
    """
    today = datetime.date.today()
    if today.month == 12:
        day = today.replace(day=31)
    day = (today.replace(month=today.month, day=1) - datetime.timedelta(days=1))
    if string:
        return day.strftime("%Y%m%d")
    return day

def yesterday(string = True):
    """Get formated yesterday.

    @param string: True to return string otherwise DateTime

    @return date as string or DateTime
    """
    today = datetime.date.today()
    day = today - datetime.timedelta(days=1)
    if string:
        return day.strftime("%Y%m%d")
    return day

def get_date_interval(date):
    """Get date internal.

    @param date internal as string, eg. 20150311:20150327

    @return list of dates
    """
    dlist = []
    if ':' not in date:
        return [date]
    
    if date.startswith(':'):
        sdate = last_day_of_month(string=False) + datetime.timedelta(days=1)
        edate = datetime.datetime.strptime(date[1:], "%Y%m%d").date()
    elif date.endswith(':'):
        sdate = datetime.datetime.strptime(date[:-1], "%Y%m%d").date()
        edate = yesterday(string=False)
    else:
        s, e = date.split(':', 1)
        sdate = datetime.datetime.strptime(s, "%Y%m%d").date()
        edate = datetime.datetime.strptime(e, "%Y%m%d").date()
    
    d = sdate
    delta = datetime.timedelta(days=1)
    while d <= edate:
        dlist.append(d.strftime("%Y%m%d"))
        d += delta
    
    return dlist

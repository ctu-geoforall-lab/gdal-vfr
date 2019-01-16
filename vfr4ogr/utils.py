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
import datetime
import mimetypes
from xml.dom.minidom import parse, parseString

try:
    from osgeo import gdal, ogr
except ImportError as e:
    sys.exit('ERROR: Import of ogr from osgeo failed. %s' % e)

from .exception import VfrError
from .logger import VfrLogger

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
        print(i)

def read_file(filename, date=None):
    """Read input file to get list of VFR files

    Raise VfrError on error.
    
    @param: file name
    @param: force datum
    
    @return file list
    """
    if not filename and filename.startswith('-'):
        raise VfrError('No input file specified')
    if not os.path.isfile(filename):
        raise VfrError("'%s' doesn't exists or it's not a file" % filename)
    
    file_list = []
    mtype = mimetypes.guess_type(filename)[0]
    if mtype is None or ('xml' not in mtype and 'zip' not in mtype):
        with open(filename, 'r') as fi:
            for line in fi.readlines():
                line = line.strip()
                if len(line) < 1 or line.startswith('#'):
                    continue # skip empty or commented lines 
                if date and not line.startswith('20'):
                    file_list.append('{}_{}'.format(date, line))
                else:
                    file_list.append(line)
    else:
        file_list.append(os.path.abspath(filename))
    
    return file_list

def parse_xml(filename):
    """Parse VFR (XML) file.

    @param filename: name of VFR file to be parsed

    @return list of items
    """
    VfrLogger.msg("Comparing OGR layers and input XML file (may take some time)...", header=True)
    if date > datetime.date(2018, 12, 7):
        from zipfile import ZipFile
        with ZipFile(filename) as zipfile:
            item = os.path.splitext(os.path.basename(filename))[0]
            with zipfile.open(item) as fd:
                content = fd.read()
    else:
        import gzip
        with gzip.open(filename) as fd:
            content = fd.read()

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
            print("+ {}".format(item))
    
    for item in list2:
        if item not in list1:
            print("- {}".format(item))

def last_day_of_month(string = True):
    """Get last day of current month.

    @param string: True to return string otherwise DateTime

    @return date as string or DateTime
    """
    today = datetime.date.today()
    date = today.replace(day=1) - datetime.timedelta(days=1)
    if string:
        return date.strftime("%Y%m%d")
    return date

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

def extension():
    """Return valid file extension"""
    return 'zip' if datetime.date.today() > datetime.date(2018, 12, 7) else 'gz'


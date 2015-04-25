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

# list supported OGR formats
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
        
        formatsList.append(driverName.replace(' ', '_'))
    
    for i in sorted(formatsList):
        print i

# check input VFR file exists
def check_file(filename):
    if not filename:
        return None
    
    if filename.startswith('-'):
        raise VfrError('No input file specified')
    if not os.path.isfile(filename):
        raise VfrError("'%s' doesn't exists or it's not a file" % filename)
    
    return filename

# parse VFR (XML) file
def parse_xml_gz(filename):
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

# compate to list of XML nodes (see parse_xml_gz())
def compare_list(list1, list2):
    for item in list1:
        if item not in list2:
            print "+ %s" % item
    
    for item in list2:
        if item not in list1:
            print "- %s" % item

# download VFR file to local disc
def download_vfr(url):
    VfrLogger.msg("Downloading %s into currect directory..." % url)
    local_file = os.path.basename(url)
    ### urllib.urlretrieve (url, local_file)
    fd = open(local_file, 'wb')
    try:
        fd.write(urllib2.urlopen(url).read())
    except urllib2.HTTPError as e:
        fd.close()
        if e.code == 404:
            error("File '%s' not found" % url)
    
    fd.close()
    
    return local_file

# get last day of current month
def last_day_of_month(string = True):
    today = datetime.date.today()
    if today.month == 12:
        day = today.replace(day=31)
    day = (today.replace(month=today.month, day=1) - datetime.timedelta(days=1))
    if string:
        return day.strftime("%Y%m%d")
    return day

# get formated yesterday 
def yesterday(string = True):
    today = datetime.date.today()
    day = today - datetime.timedelta(days=1)
    if string:
        return day.strftime("%Y%m%d")
    return day

# get date internal
def get_date_interval(date):
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

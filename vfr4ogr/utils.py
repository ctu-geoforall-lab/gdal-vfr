import os
import sys
import gzip
import urllib
import datetime
import logging

from xml.dom.minidom import parse, parseString

logger = logging.getLogger()
logFile = 'log.%d' % os.getpid()
logger.addHandler(logging.FileHandler(logFile, delay = True))

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

# check if log file exists and print message about that
def check_log():
    if os.path.exists(logFile):
        message("NOTICE: CHECK OUT '%s' FOR WARNINGS!" % logFile)

# check input VFR file exists
def check_file(filename):
    if not filename:
        return None
    
    if filename.startswith('-'):
        fatal('No input file specified')
    if not os.path.isfile(filename):
        fatal("'%s' doesn't exists or it's not a file" % filename)
    
    return filename

# print fatal error message and exit
def fatal(msg):
    sys.exit('ERROR: ' + str(msg))

# print warning message
def warning(msg):
    # sys.stderr.write('WARNING: %s%s' % (str(msg), os.linesep))
    logger.warning(msg)

# print error message
def error(msg):
    sys.stderr.write('ERROR: %s%s' % (str(msg), os.linesep))

# print message to stdout
def message(msg):
    sys.stdout.write('-' * 80 + os.linesep)
    sys.stdout.write(msg + os.linesep)
    sys.stdout.write('-' * 80 + os.linesep)
    sys.stdout.flush()
    
# parse VFR (XML) file
def parse_xml_gz(filename):
    message("Comparing OGR layers and input XML file (may take some time)...")
    infile = gzip.open(filename)
    content = infile.read()
    
    # parse xml file content
    dom = parseString(content)
    data = dom.getElementsByTagName('vf:Data')[0]
    if data is None:
        fatal("vf:Data not found")

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
    message("Downloading %s into currect directory..." % url)
    local_file = os.path.basename(url)
    urllib.urlretrieve (url, local_file)
    
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

# remove specified option from list
def remove_option(options, name):
    i = 0
    for opt in options:
        if opt.startswith(name):
            del options[i]
            return 
        i += 1

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

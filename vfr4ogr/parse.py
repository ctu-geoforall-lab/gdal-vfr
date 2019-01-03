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

from .utils import read_file, last_day_of_month, yesterday, get_date_interval, list_formats, extension
from .exception import VfrErrorCmd

def parse_cmd(optdir):
    """Parse command.

    @param optdir: parsed options

    @return file list
    """
    if hasattr(optdir, "format") and optdir.format:
        optdir.format = optdir.format.replace('_', ' ')
    else:
        optdir.format = None

    if not hasattr(optdir, "dsn"):
        optdir.dsn = None

    if optdir.format is None and \
            ((hasattr(optdir, "dsn") and optdir.dsn) or \
                 (hasattr(optdir, "dbname") and optdir.dbname)):
        raise VfrErrorCmd("Output format not defined")

    if optdir.list:
        if not optdir.dbname:
            raise VfrErrorCmd("--dbname required")
        return 0

    filename = optdir.file
    date = optdir.date
    ftype = optdir.type
    
    # check required options
    if not filename and not ftype:
        raise VfrErrorCmd("--file or --type required")
    if filename and ftype:
        raise VfrErrorCmd("--file and --type are mutually exclusive")

    date_list = []
    if ftype and not date:
        if ftype.startswith('ST_Z'):
            date_list = [yesterday()]
        else:
            date_list = [last_day_of_month()]
    elif ftype and date and ':' in date:
            if ftype.startswith('ST_Z'):
                date_list = get_date_interval(date)
            else:
                raise VfrErrorCmd("Date interval is valid only for '--type ST_ZXXX'")
    elif date:
        date_list = [date]
    
    if optdir.overwrite and optdir.append:
        raise VfrErrorCmd("--append and --overwrite are mutually exclusive")
    
    if optdir.layer:
        optdir.layer = optdir.layer.split(',')
    else:
        optdir.layer = []

    if filename:               # --filename
        file_list = read_file(filename)
    else:                      # --date && --type
        file_list = []
        for d in date_list:
            file_list.append("{}_{}.xml.{}".format(d, ftype, extension()))
    
    if not file_list:
        raise VfrErrorCmd("Empty date range")

    return file_list

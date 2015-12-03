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
import getopt

from utils import read_file, last_day_of_month, yesterday, get_date_interval

def get_opt(argv, flags, params, optdir):
    """Parse options.

    @param argv: arguments
    @param flags: flags
    @param params: parameters
    @param optdir: option directory to be set up
    """
    try:
        opts, args = getopt.getopt(argv[1:], flags, params)
    except getopt.GetoptError as err:
        sys.exit(str(err))
    
    for o, a in opts:
        so = o[2:]
        if o == "--file":
            optdir['filename'] = a
        elif o == "--date":
            optdir['date'] = a
        elif o == "--type":
            optdir['ftype'] = a
        elif o in ("-h", "--help"):
            raise getopt.GetoptError("")
        elif o in ("-o", "--overwrite"):
            optdir['overwrite'] = True
        elif o in ("-a", "--append"):
            optdir['append'] = True
        elif o in ("-e", "--extended"):
            optdir['extended'] = True
        elif o == "-d":
            optdir['download'] = True
        elif o == "-s":
            optdir['schema_per_file'] = True
        elif o == "-g":
            optdir['nogeomskip'] = True
        elif o == "-l":
            optdir['list'] = True
        elif o == "-f": # unused
            list_formats() # TODO
            sys.exit(0)
        elif o == "--format":
            optdir['format'] = a.replace('_', ' ')
        elif so in optdir:
            if a:
                optdir[so] = a
            else:
                optdir[so] = True
        else:
            sys.exit("unhandled option: %s" % o)

def parse_cmd(argv, flags, params, optdir):
    """Parse command.

    @param argv: arguments
    @param flags: flags
    @param params: parameters
    @param optdir: option directory to be set up

    @return file list
    """
    get_opt(argv, flags, params, optdir)

    if optdir['list']:
        if not optdir['dbname']:
            raise getopt.GetoptError("--dbname required")
        return 0
    
    filename = optdir.get('filename', None)
    date = optdir.get('date', None)
    ftype = optdir.get('ftype', None)
    
    # check required options
    if not filename and not ftype:
        raise getopt.GetoptError("--file or --type required")
    if filename and ftype:
        raise getopt.GetoptError("--file and --type are mutually exclusive")

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
                raise getopt.GetoptError("Date interval is valid only for '--type ST_ZXXX'")
    elif date:
        date_list = [date]
    
    if optdir['overwrite'] and optdir.get('append', False):
        raise getopt.GetoptError("--append and --overwrite are mutually exclusive")
    
    if optdir['layer']:
        optdir['layer'] = optdir['layer'].split(',')

    if filename:               # --filename
        file_list = read_file(filename, date)
    else:                      # --date && --type
        file_list = []
        for d in date_list:
            file_list.append("%s_%s.xml.gz" % (d, ftype))
    
    base_url = "http://vdp.cuzk.cz/vymenny_format/"
        
    force_date = date
    for i in range(0, len(file_list)):
        line = file_list[i]
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

        if not line.startswith('http'):
            # add base url if missing
            base_url_line = base_url
            if (ftype and ftype != 'ST_UVOH') or 'ST_UVOH' not in line:
                base_url_line += "soucasna/"
            else:
                base_url_line += "specialni/"
            
            line = base_url_line + line

        if not line.endswith('.xml.gz'):
            # add extension if missing
            line += '.xml.gz'
                    
        file_list[i] = line
        
    if not file_list:
        raise getopt.GetoptError("Empty date range")

    return file_list

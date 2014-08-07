import os
import sys
import getopt

from utils import fatal, message, check_file, download_vfr, last_day_of_month, yesterday, get_date_interval
from ogr import list_formats

def parse_cmd(argv, flags, params, optdir):
    try:
        opts, args = getopt.getopt(argv[1:], flags, params)
    except getopt.GetoptError as err:
        sys.exit(str(err))
    
    filename = date = ftype = None
    for o, a in opts:
        so = o[2:]
        if o == "--file":
            filename = a
        elif o == "--date":
            optdir['date'] = date = a
        elif o == "--type":
            ftype = a
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
        elif o == "-f": # unused
            list_formats()
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
    
    # check required options
    if not filename and not ftype:
        raise getopt.GetoptError("--file or --type required")
    if filename and ftype:
        raise getopt.GetoptError("--file and --type are mutually exclusive")

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
    else:
        date_list = [date]
    
    if optdir['overwrite'] and optdir.get('append', False):
        raise getopt.GetoptError("--append and --overwrite are mutually exclusive")
    
    if optdir['layer']:
        optdir['layer'] = optdir['layer'].split(',')
    
    if filename:
        # is file a valid VFR file
        filename = check_file(filename)
    else: # --date & --type
        flist = []
        for d in date_list:
            url = "http://vdp.cuzk.cz/vymenny_format/soucasna/%s_%s.xml.gz" % (d, ftype)
            if optdir['download']:
                flist.append(download_vfr(url))
            else:
                flist.append("/vsicurl/" + url)
        if not flist:
            raise getopt.GetoptError("Empty date range")
        
        filename = os.linesep.join(flist)
        
    if not filename:
        raise getopt.GetoptError("Invalid input file")

    return filename

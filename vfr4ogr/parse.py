import sys
import getopt

from utils import fatal, message, check_file, download_vfr, last_day_of_month
from ogr import list_formats

def parse_cmd(argv, flags, params, optdir):
    try:
        opts, args = getopt.getopt(argv[1:], flags, params)
    except getopt.GetoptError as err:
        sys.exit(str(err))
    
    filename = date = ftype = None
    for o, a in opts:
        so = o[2:]
        if so in optdir:
            if a:
                optdir[so] = a
            else:
                optdir[so] = True
        elif o == "--file":
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
        elif o == "-f": # unused
            list_formats()
            sys.exit(0)
        else:
            sys.exit("unhandled option: %s" % o)
    
    if not filename and not ftype:
        raise getopt.GetoptError("--file or --type required")
    if filename and ftype:
        raise getopt.GetoptError("--file and --type are mutually exclusive")
    if ftype and not date:
        date = last_day_of_month()
    if optdir['overwrite'] and optdir.get('append', False):
        raise getopt.GetoptError("--append and --overwrite are mutually exclusive")
    
    if optdir['layer']:
        optdir['layer'] = optdir['layer'].split(',')
    
    if filename:
        filename = check_file(filename)
    else: # --date & --type
        url = "http://vdp.cuzk.cz/vymenny_format/soucasna/%s_%s.xml.gz" % (date, ftype)
        if optdir['download']:
            filename = download_vfr(url)
        else:
            message("Reading %s..." % url)
            filename = "/vsicurl/" + url
    
    if not filename:
        raise getopt.GetoptError("Ivalid input file")
    
    return filename

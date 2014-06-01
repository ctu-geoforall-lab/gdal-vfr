import sys
import getopt

from utils import fatal, message, check_file, download_vfr, last_day_of_month
from ogr import list_formats

def parse_cmd(argv, flags, params, outdir):
    try:
        opts, args = getopt.getopt(argv[1:], flags, params)
    except getopt.GetoptError as err:
        sys.exit(str(err))
    
    filename = date = ftype = None
    for o, a in opts:
        so = o[2:]
        if so in outdir:
            if a:
                outdir[so] = a
            else:
                outdir[so] = True
        elif o == "--file":
            filename = a
        elif o == "--date":
            date = a
        elif o == "--type":
            ftype = a
        elif o in ("-h", "--help"):
            raise getopt.GetoptError("")
        elif o in ("-o", "--overwrite"):
            outdir['overwrite'] = True
        elif o in ("-a", "--append"):
            outdir['append'] = True
        elif o in ("-e", "--extended"):
            outdir['extended'] = True
        elif o == "-d":
            outdir['download'] = True
        elif o == "-s":
            outdir['schema_per_file'] = True
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
    if outdir['overwrite'] and outdir.get('append', False):
        raise getopt.GetoptError("--append and --overwrite are mutually exclusive")
    
    if outdir['layer']:
        outdir['layer'] = outdir['layer'].split(',')
    
    if filename:
        filename = check_file(filename)
    else: # --date & --type
        url = "http://vdp.cuzk.cz/vymenny_format/soucasna/%s_%s.xml.gz" % (date, ftype)
        if outdir['download']:
            filename = download_vfr(url)
        else:
            message("Reading %s..." % url)
            filename = "/vsicurl/" + url
    
    if not filename:
        raise getopt.GetoptError("Ivalid input file")
    
    return filename

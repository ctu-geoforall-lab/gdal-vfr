import sys
import getopt

from utils import fatal, message, check_file
from vfr import list_formats

def parse_cmd(argv, flags, params, outdir):
    try:
        opts, args = getopt.getopt(argv[1:], flags, params)
    except getopt.GetoptError as err:
        print str(err) 
        return None
    
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
        elif o in ("-e", "--extended"):
            outdir['extended'] = True
        elif o == "-f": # unused
            list_formats()
            sys.exit(0)
        else:
            assert False, "unhandled option: %s" % o
    
    if not filename and not date:
        raise getopt.GetoptError("--file or --date required")
    if filename and date:
        raise getopt.GetoptError("--file and --date are mutually exclusive")
    if date and not ftype:
        raise getopt.GetoptError("--ftype required")
    
    if outdir['layer']:
        outdir['layer'] = outdir['layer'].split(',')
    
    if filename:
        filename = check_file(filename)
    else:
        url = "http://vdp.cuzk.cz/vymenny_format/soucasna/%s_%s.xml.gz" % (date, ftype)
        message("Downloading %s..." % url)
        filename = "/vsicurl/" + url
    
    if not filename:
        raise getopt.GetoptError("Ivalid input file")
    
    return filename

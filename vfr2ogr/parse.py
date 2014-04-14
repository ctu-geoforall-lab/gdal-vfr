import getopt

from utils import *
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
            return None
        elif o == "-f": # unused
            list_formats()
            sys.exit(0)
        else:
            assert False, "unhandled option: %s" % o
    
    if not filename and not date:
        fatal("--file or --date requested")
    if filename and date:
        fatal("--file and --date are mutually exclusive")
    if date and not ftype:
        fatal("--ftype requested")
    
    if filename:
        # check if input VFR file exists
        filename = check_file(filename)
    else:
        url = "http://vdp.cuzk.cz/vymenny_format/soucasna/%s_%s.xml.gz" % (date, ftype)
        message("Downloading %s..." % url)
        filename = "/vsicurl/" + url
        
    return filename

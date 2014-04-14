import os
import sys

def check_file(filename):
    if filename.startswith('-'):
        fatal('No input file specified')
    if not os.path.isfile(filename):
        fatal("'%s' doesn't exists or it's not a file" % filename)
    
    return filename

def fatal(msg):
    sys.exit('ERROR: ' + msg)

def message(msg):
    sys.stderr.write('-' * 80 + os.linesep)
    sys.stderr.write(msg + os.linesep)
    sys.stderr.write('-' * 80 + os.linesep)

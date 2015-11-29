###############################################################################
#
# VFR importer based on GDAL library
#
# Author: Martin Landa <landa.martin gmail.com>
#
# Licence: MIT/X
#
###############################################################################

import logging
import sys
import os

logFile = None
###logFile = 'log.%d' % os.getpid()
###logger.addHandler(logging.FileHandler(logFile, delay = True))

class Logger(logging.getLoggerClass()):
    def msg(self, msg):
        """Print messages to stdout
        """
        sys.stdout.write('-' * 80 + os.linesep)
        sys.stdout.write(msg + os.linesep)
        sys.stdout.write('-' * 80 + os.linesep)
        sys.stdout.flush()
    
VfrLogger = Logger('Vfr')
VfrLogger.addHandler(logging.StreamHandler(sys.stderr))

# check if log file exists and print message about that
def check_log():
    if logFile and os.path.exists(logFile):
        VfrLogger.msg("NOTICE: CHECK OUT '%s' FOR WARNINGS!" % logFile)

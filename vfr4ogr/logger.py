import logging
import sys
import os

logFile = None
###logFile = 'log.%d' % os.getpid()
###logger.addHandler(logging.FileHandler(logFile, delay = True))

class Logger(logging.getLoggerClass()):
    # print message to stdout
    def msg(self, msg):
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


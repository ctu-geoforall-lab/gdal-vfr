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
import types

logFile = None
MSG_LEVEL = 15
logging.addLevelName(MSG_LEVEL, "MSG")

# python 2.7 hack (in Python 3 can be replaced by 'terminates')
def customEmit(self, record):
    try:
        msg = self.format(record)
        if not hasattr(types, "UnicodeType"): # if no unicode support...
            self.stream.write(msg)
        else:
            try:
                if getattr(self.stream, 'encoding', None) is not None:
                    self.stream.write(msg.encode(self.stream.encoding))
                else:
                    self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
        self.flush()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        self.handleError(record)

class NoNewLineLogHandler(logging.StreamHandler):
    def __init__(self, *args):

        setattr(logging.StreamHandler, logging.StreamHandler.emit.__name__, customEmit)

        logging.StreamHandler.__init__(self, *args)
        
class Logger(logging.getLoggerClass()):
    def __init__(self, name, level=logging.NOTSET):
        super(Logger, self).__init__(name)
        self.setLevel(level)
        
    def msg(self, msg, header=False, style='-', *args, **kwargs):
        """Print messages to stdout
        """
        if not self.isEnabledFor(MSG_LEVEL):
            return
        
        if header:
            message="{}\n{}\n{}\n".format(style * 80, msg, style * 80)
        else:
            message = msg

        self._log(MSG_LEVEL, message, args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self._log(logging.WARNING, 'WARNING: ' + message + os.linesep, args, **kwargs)

    def error(self, message, *args, **kwargs):
        self._log(logging.ERROR, 'ERROR: ' + message + os.linesep, args, **kwargs)

    def debug(self, message, *args, **kwargs):
        if not self.isEnabledFor(logging.DEBUG):
            return
        self._log(logging.DEBUG, 'DEBUG: ' + message + os.linesep, args, **kwargs)

VfrLogger = Logger('Vfr')
VfrLogger.msg = VfrLogger.msg
VfrLogger.addHandler(NoNewLineLogHandler(sys.stderr))
VfrLogger.setLevel(MSG_LEVEL)
#VfrLogger.setLevel(logging.DEBUG)

# check if log file exists and print message about that
def check_log():
    if logFile and os.path.exists(logFile):
        VfrLogger.msg("NOTICE: CHECK OUT '%s' FOR WARNINGS!" % logFile, header=True)

from functools import wraps
import logging
from ui.utils import ErrorDialog

"""
Logging
"""


class MaryLogger(logging.Logger):

    def __init__(self, name):
        super().__init__(name)
        self.setLevel(logging.DEBUG)
        log_filename = './logs/marytreat.log'
        with open(log_filename, 'w'): # clear file contents
            pass
        fh = logging.FileHandler(log_filename, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        self.addHandler(fh)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, args, **kwargs)
        ErrorDialog(msg)

    def critical(self, msg, *args, **kwargs):
        self._log(logging.CRITICAL, msg, args, **kwargs)
        ErrorDialog(msg)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        """
        Delegate an exception call to the underlying logger.
        """
        self.log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)
        ErrorDialog(msg)


logging.setLoggerClass(MaryLogger)
logger = logging.getLogger(__name__)


"""
Auxiliary debugging functions
"""


def debug(func):
    name = func.__qualname__

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug('Running ' + name)
        return func(*args, **kwargs)
    return wrapper


def debugmethods(cls):
    for k, v in vars(cls).items():
        if callable(v):
            type(v)
            setattr(cls, k, debug(v))
    return cls

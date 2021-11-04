import logging

class NetAppLog:

    def __init__(self, name="", netapp_name=""):
        self.name = name
        self.netapp_name = netapp_name
        self.log = self.initLog()

    def initLog(self, console=True):

        # Configure logger options
        logger = logging.getLogger(self.netapp_name)

        # Set global log level
        logger.setLevel(logging.DEBUG)

        # Formnat logs
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # console logging
        if console is True:
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            ch.setLevel(logging.DEBUG)
            logger.addHandler(ch)

        return logger

    def info(self, msg, *arg):
        for i in arg:
            msg = msg + ' - ' + i         
        self.log.info(msg)

    def debug(self, msg, *arg):
        for i in arg:
            msg = msg + ' - ' + i         
        self.log.debug(msg)

    def warning(self, msg, *arg):
        for i in arg:
            msg = msg + ' - ' + i         
        self.log.warning(msg)
    
    def error(self, msg, *arg):
        for i in arg:
            msg = msg + ' - ' + i         
        self.log.error(msg)
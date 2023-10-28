#! /usr/bin/env python3

import time
import logging
import logging.handlers

logger = logging.getLogger('TestLogger')
logger.setLevel(logging.INFO)

handler = logging.handlers.SysLogHandler(address='/dev/log')
logger.addHandler(handler)

logger.info('Starting testlogging.')
for i in range(0,1000):
    logger.info(i)
    time.sleep(1/1000000) # log entry every 1us

logger.info('Finished testlogging.')

#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent


logger = logging.getLogger(__name__)


class Simple(Agent):

    def _loop(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(10)
            logger.debug("loop")


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Simple()
    run()

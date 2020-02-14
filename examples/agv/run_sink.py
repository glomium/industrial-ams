#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import time

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent


class Sink(Agent):

    def simulation_start(self):
        pass

    def _loop(self):
        while True:
            time.sleep(10)


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Sink()
    run()

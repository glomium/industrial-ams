#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Source(Agent):
    pass


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.INFO))
    run = Source()
    run()

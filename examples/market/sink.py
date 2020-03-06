#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent
from iams.market import ExecuteInterface
from iams.proto import market_pb2

random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Sink(ExecuteInterface, Agent):

    def _loop(self):
        pass

    def order_validate(self, order, step, eta):
        return market_pb2.OrderCost()

    def order_start(self, order, steps, eta):
        return True

    def order_cancel(self, order):
        return True


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Sink()
    run()

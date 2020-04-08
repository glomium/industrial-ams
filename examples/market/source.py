#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent
from iams.market import RootInterface
from iams.proto import market_pb2


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Source(RootInterface, Agent):

    def order_update_config(self, retries=0):
        pass

    def order_get_data(self):
        return 0.0, [market_pb2.Step()]

    def order_agent_labels(self):
        yield ['iams.image=iams_market_sink']

    # callback not used in simulation
    def order_canceled(self):  # pragma: no cover
        pass

    # callback not used in simulation
    def order_finished(self):  # pragma: no cover
        pass

    # callback not used in simulation
    def order_canceled(self):  # pragma: no cover
        pass

    # callback not used in simulation
    def order_reassigned(self):  # pragma: no cover
        pass

    def order_cancel(self):  # from servicer
        pass

    def order_start_step(self, step):  # from servicer
        pass

    def order_finish_step(self, step):  # from servicer
        pass


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Source()
    run()

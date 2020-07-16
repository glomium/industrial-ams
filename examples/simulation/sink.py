#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent
# from iams.mixins.arangodb import TopologyMixin
# from iams.utils.auth import permissions
from iams.market import MarketWorkerInterface

# import example_pb2
import example_pb2_grpc


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Servicer(example_pb2_grpc.SinkServicer):

    def __init__(self, parent):
        self.parent = parent


class Sink(MarketWorkerInterface, Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.order_missed = 0
        self.order_consumed = 0
        self.buffer_storage = []
        self.started = False
        self.eta = None

    def _loop(self):
        pass

    def grpc_setup(self):
        self._grpc.add(example_pb2_grpc.add_SinkServicer_to_server, self.servicer)

    def simulation_start(self):
        # we start the simulation on the sink only if the first order was received
        pass

    def topology_get_abilities(self):
        return ['sink']

    def topology_default_edge(self):
        return "buffer"

    def topology_edges(self):
        return []

    def get_next_time(self):
        while True:
            time = random.gauss(self._config["mean"], self._config["sigma"])
            if time > 0.0:
                return time

    def consume_part(self):
        try:
            # get the first part in buffer
            order = self.buffer_storage.pop(0)

            # TODO tell ams to kill order or order to kill itself

            self.order_consumed += 1
            logger.info(
                "consumed order: %s - queue %s/%s",
                order,
                len(self.buffer_storage),
                self._config["buffer"],
            )
            self._simulation.log("consumed order")
            missed = 0
            consumed = 1

        except IndexError:
            # buffer empty
            self.order_missed += 1
            logger.info("buffer empty - stopping")
            self._simulation.log("buffer empty")
            missed = 1
            consumed = 0

        self._simulation.metric({
            "total_consumed": self.order_consumed,
            "total_missed": self.order_missed,
            "consumed": consumed,
            "missed": missed,
            "queue": len(self.buffer_storage),
        })

        # schedule next event or stop execution
        if consumed:
            self.eta = self._simulation.schedule(self.get_next_time(), 'consume_part')
        else:
            self.started = False
            self.eta = None


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Sink()
    run()

#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

# import grpc

# from google.protobuf.empty_pb2 import Empty

from iams.helper import get_logging_config
from iams.interface import Agent
# from iams.utils.auth import permissions

# import example_pb2
import example_pb2_grpc


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Servicer(example_pb2_grpc.SourceServicer):

    def __init__(self, parent):
        self.parent = parent


class Source(Agent):
    """
    Source generates orders in intervalls
    Source have a bufferstorage of X parts, if the buffer is full the generation is skipped
    Source count generated and missed generation of orders
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.order_missed = 0
        self.order_generated = 0
        self.buffer_storage = []

    def _loop(self):
        pass

    def grpc_setup(self):
        self._grpc.add(example_pb2_grpc.add_SourceServicer_to_server, self.servicer)

    def simulation_start(self):
        self._simulation.schedule(self.get_next_time(), 'generate_part')

    def get_next_time(self):
        while True:
            time = random.gauss(self._config["mean"], self._config["sigma"])
            if time > 0.0:
                return time

    def generate_part(self):
        name = "order_%s" % random.getrandbits(40).to_bytes(5, byteorder="little").hex()

        if len(self.buffer_storage) == self._config["buffer"]:
            self.order_missed += 1
            logger.info("missed order: %s", name)
            self._simulation.log("missed order")
            missed = 1
            generated = 0
        else:
            # generate order agent at AMS
            valid, response = self._iams.call_create(
                name=name,
                image="iams_simulation_order",
                version="local",
                config={"position": self._iams.agent},
            )

            if valid:
                self.order_generated += 1
                self.buffer_storage.append((self._simulation.time, response.name))
                logger.info(
                    "generated order: %s - queue %s/%s",
                    name,
                    len(self.buffer_storage),
                    self._config["buffer"],
                )
                self._simulation.log("generated order")
            else:
                raise RuntimeError('AMS responded with error code %s' % response)

        self._simulation.metric({
            "total_generated": self.order_generated,
            "total_missed": self.order_missed,
            "generated": generated,
            "missed": missed,
            "queue": len(self.buffer_storage),
        })


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.INFO))
    run = Source()
    run()

#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interfaces import Agent
from iams.utils.auth import permissions

import example_pb2
import example_pb2_grpc


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Servicer(example_pb2_grpc.SinkServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def get_coordinates(self, request, response):
        return example_pb2.Data(x=self.parent._config["position"]["x"], y=self.parent._config["position"]["y"])

    @permissions(has_agent=True)
    def put_part(self, request, response):
        if self.parent.storage >= self.parent._config["buffer"]:
            # queue full, wait for next event to unload
            return example_pb2.Time(time=self.parent.eta - self.parent._simulation.time)
        else:
            # start consumation of products after the first product arrives
            if not self.parent.started:
                self.parent._simulation.schedule(self.parent.get_next_time(), 'consume_part')
                self.parent.started = True
            # queue not full -> dont wait
            self.parent.storage += 1
            return example_pb2.Time()


class Sink(Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.part_missed = 0
        self.part_consumed = 0
        self.storage = 0
        self.started = False
        self.eta = None

    def _loop(self):
        pass

    def grpc_setup(self):
        self._grpc.add(example_pb2_grpc.add_SinkServicer_to_server, self.servicer)

    def get_next_time(self):
        time = random.gauss(self._config["mean"], self._config["sigma"])
        if time > 0:
            return time
        return 0.0

    def consume_part(self):
        if self.storage == 0:
            self.part_missed += 1
            logger.info("missed part")
            self._simulation.log("missed part")
            self._simulation.metric({
                "total_consumed": self.part_consumed,
                "total_missed": self.part_missed,
                "consumed": 0,
                "missed": 1,
                "queue": self.storage,
            })
        else:
            self.part_consumed += 1
            self.storage -= 1
            logger.info("part consumed - queue %s/%s", self.storage, self._config["buffer"])
            self._simulation.log("consumed part")
            self._simulation.metric({
                "total_consumed": self.part_consumed,
                "total_missed": self.part_missed,
                "consumed": 1,
                "missed": 0,
                "queue": self.storage,
            })

        # schedule next consume
        self.eta = self._simulation.schedule(self.get_next_time(), 'consume_part')


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Sink()
    run()

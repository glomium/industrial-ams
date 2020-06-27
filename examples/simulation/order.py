#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging

from logging.config import dictConfig
# from math import sqrt

# import grpc

# from google.protobuf.empty_pb2 import Empty

from iams.helper import get_logging_config
from iams.interface import Agent
# from iams.utils.auth import permissions

# import example_pb2
import example_pb2_grpc


logger = logging.getLogger(__name__)


class Servicer(example_pb2_grpc.OrderServicer):

    def __init__(self, parent):
        self.parent = parent


class Order(Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)

    def _loop(self):
        pass

    def grpc_setup(self):
        self._grpc.add(example_pb2_grpc.add_OrderServicer_to_server, self.servicer)

    def simulation_start(self):
        pass


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.INFO))
    run = Order()
    run()

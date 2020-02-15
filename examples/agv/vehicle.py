#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
# import time

from logging.config import dictConfig

from iams.helper import get_logging_config
from iams.interface import Agent

import agv_pb2_grpc


class Servicer(agv_pb2_grpc.SinkServicer):

    def __init__(self, parent):
        self.parent = parent

    def get_eta(self, request, context):
        pass

    def drive(self, request, context):
        pass


class Vehicle(Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.x = self._config["position"]["x"]
        self.y = self._config["position"]["y"]

    def grpc_setup(self):
        self._grpc.add(agv_pb2_grpc.add_VehicleServicer_to_server, self.servicer)


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Vehicle()
    run()

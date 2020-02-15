#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

import grpc

from google.protobuf.empty_pb2 import Empty

from iams.agent import framework_channel
from iams.helper import get_logging_config
from iams.interface import Agent

import agv_pb2
import agv_pb2_grpc


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Servicer(agv_pb2_grpc.SourceServicer):

    def __init__(self, parent):
        self.parent = parent

    def reserve_next(self, request, response):
        self.parent.on_route = True
        return Empty()

    def next_order(self, request, response):
        if not self.parent.on_route and self.parent.part_storage:
            return agv_pb2.Time(time=self.parent.part_storage[0])
        else:
            return agv_pb2.Time()

    def get_part(self, request, response):
        time, data = self.parent.part_storage.pop(0)
        return data


class Source(Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.part_missed = 0
        self.part_generated = 0
        self.part_storage = []
        self.on_route = False

    def simulation_start(self):
        # schedule next event with framework
        self._simulation.schedule(0.0, 'get_cache')
        self._simulation.schedule(self.get_next_time(), 'generate_part')

    def grpc_setup(self):
        self._grpc.add(agv_pb2_grpc.add_SourceServicer_to_server, self.servicer)

    def get_cache(self):
        self.sinks = []
        self.vehicles = []

        # get all sinks
        for sink in self._iams.get_agents(['iams.image=example_sink']):
            self.sinks.append(sink.name)
            with framework_channel(sink.name, credentials=self.parent._credentials) as channel:
                stub = agv_pb2_grpc.SinkStub(channel)
                response = stub.get_coodinates(Empty())

            response.name = sink.name
            self.sinks.append(response)
            logger.info("got sink: %s", response)

        # get all vehicles
        for vehicle in self._iams.get_agents(['iams.image=example_vehicle']):
            self.vehicles.append(vehicle.name)
        logger.info("got vehicles: %s", self.vehicles)

    def get_next_time(self):
        time = random.gauss(self._config.mean, self._config.sigma)
        if time > 0:
            return time
        return 0.0

    def generate_part(self):
        if len(self.part_storage) == self._config.buffer:
            self.part_missed += 1
            logger.info("missed part")
        else:
            self.part_generated += 1
            sink = random.choice(self.sinks)
            logger.info("selected sink: %s", sink)
            self.storage.append((self.parent._simulation.time, sink))

            # call all vehicles and select nearest first
            times = {}
            request = agv_pb2.Data(x=self._config.position.x, y=self._config.position.y)
            for vehicle in self.vehicles:
                try:
                    with framework_channel(vehicle, credentials=self.parent._credentials) as channel:
                        stub = agv_pb2_grpc.VehicleStub(channel)
                        response = stub.get_eta(request)
                        times[vehicle] = response.time
                except grpc.RpcError:
                    pass

            # select nearest vehicle first
            if times:
                vehicle = min(times, key=times.get)

                with framework_channel(vehicle, credentials=self.parent._credentials) as channel:
                    stub = agv_pb2_grpc.VehicleStub(channel)
                    stub.drive(request)
                    self.on_route = True

        # schedule next part generation
        # self._simulation.schedule(self.get_next_time(), 'generate_part')


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Source()
    run()

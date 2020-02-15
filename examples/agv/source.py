#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import random
import os

from logging.config import dictConfig

import grpc

from google.protobuf.empty_pb2 import Empty

from iams.helper import get_logging_config
from iams.interface import Agent
from iams.utils.auth import permissions

import agv_pb2
import agv_pb2_grpc


random.seed(os.environ.get("IAMS_SEED", None))
logger = logging.getLogger(__name__)


class Servicer(agv_pb2_grpc.SourceServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def reserve_next(self, request, context):
        self.parent.on_route += 1
        return agv_pb2.Data(x=self.parent._config["position"]["x"], y=self.parent._config["position"]["y"])

    @permissions(has_agent=True)
    def next_order(self, request, context):
        if self.parent.on_route < len(self.parent.storage):
            return agv_pb2.Time(time=self.parent.storage[self.parent.on_route][0])
        context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "resource empty")

    @permissions(has_agent=True)
    def get_part(self, request, context):
        time, data = self.parent.storage.pop(0)
        self.parent.on_route -= 1
        return data


class Source(Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.part_missed = 0
        self.part_generated = 0
        self.storage = []
        self.on_route = 0

    def simulation_start(self):
        # schedule next event with framework
        self._simulation.schedule(0.0, 'get_cache')
        self._simulation.schedule(self.get_next_time(), 'generate_part')

    def grpc_setup(self):
        self._grpc.add(agv_pb2_grpc.add_SourceServicer_to_server, self.servicer)

    def get_cache(self):
        # get all sinks
        sinks = []
        for sink in self._iams.get_agents(['iams.image=example_sink']):
            sinks.append(sink.name)
        sinks = sorted(sinks)

        self.sinks = []
        for sink in sinks:
            with self._channel(sink) as channel:
                stub = agv_pb2_grpc.SinkStub(channel)
                response = stub.get_coordinates(Empty())

            response.name = sink
            self.sinks.append(response)
            logger.info("got sink: %s", response)

        # get all vehicles
        self.vehicles = []
        for vehicle in self._iams.get_agents(['iams.image=example_vehicle']):
            self.vehicles.append(vehicle.name)
        self.vehicles = sorted(self.vehicles)

        logger.info("got vehicles: %s", self.vehicles)

    def get_next_time(self):
        time = random.gauss(self._config["mean"], self._config["sigma"])
        if time > 0:
            return time
        return 0.0

    def generate_part(self):
        if len(self.storage) == self._config["buffer"]:
            self.part_missed += 1
            logger.info("missed part")
        else:
            self.part_generated += 1
            sink = random.choice(self.sinks)
            self.storage.append((self._simulation.time, sink))
            logger.info("generated part: %s - queue %s/%s", sink.name, len(self.storage), self._config["buffer"])

            # call all vehicles and select nearest first
            times = {}
            request = agv_pb2.Data(x=self._config["position"]["x"], y=self._config["position"]["y"])
            for vehicle in self.vehicles:
                try:
                    with self._channel(vehicle) as channel:
                        stub = agv_pb2_grpc.VehicleStub(channel)
                        response = stub.get_eta(request)
                        times[vehicle] = response.time
                except grpc.RpcError:
                    pass

            logger.debug("free vehicles: %s", times)

            # select nearest vehicle first
            if times:
                vehicle = min(times, key=times.get)
                logger.info("calling vehicle: %s", vehicle)

                with self._channel(vehicle) as channel:
                    stub = agv_pb2_grpc.VehicleStub(channel)
                    stub.drive(request)
                    self.on_route += 1

        # schedule next part generation
        self._simulation.schedule(self.get_next_time(), 'generate_part')


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.INFO))
    run = Source()
    run()

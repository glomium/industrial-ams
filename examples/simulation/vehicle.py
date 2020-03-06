#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging

from logging.config import dictConfig
from math import sqrt

import grpc

from google.protobuf.empty_pb2 import Empty

from iams.helper import get_logging_config
from iams.interface import Agent
from iams.utils.auth import permissions

import simulation_pb2
import simulation_pb2_grpc


logger = logging.getLogger(__name__)


class Servicer(simulation_pb2_grpc.SinkServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def get_eta(self, request, context):
        if not self.parent.idle:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "vehicle is working")

        return simulation_pb2.Time(
            time=self.parent.get_eta(request.x, request.y),
        )

    @permissions(has_agent=True)
    def drive(self, request, context):
        self.parent._simulation.schedule(self.parent.get_eta(request.x, request.y), 'arrive_at_source')
        self.parent.x = request.x
        self.parent.y = request.y
        self.parent.idle = False
        self.parent.station = context._agent

        return Empty()


class Vehicle(Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)
        self.unload = self._config["unload"]
        self.load = self._config["load"]
        self.speed = self._config["speed"]
        self.x = self._config["position"]["x"]
        self.y = self._config["position"]["y"]
        self.idle = True
        self.station = None

    def grpc_setup(self):
        self._grpc.add(simulation_pb2_grpc.add_VehicleServicer_to_server, self.servicer)

    def simulation_start(self):
        self.sources = []

        # get all sources
        for source in self._iams.get_agents(['iams.image=example_source']):
            self.sources.append(source.name)
        self.sources = sorted(self.sources)
        logger.info("got sources: %s", self.sources)

    def get_eta(self, x, y):
        return sqrt((self.x - x)**2 + (self.y - y)**2) / self.speed

    def arrive_at_source(self):
        self._simulation.schedule(self.load, 'pick_part')

    def pick_part(self):
        with self._channel(self.station) as channel:
            stub = simulation_pb2_grpc.SourceStub(channel)
            response = stub.get_part(Empty())
        eta = self.get_eta(response.x, response.y)
        logger.info("part picked up at %s", self.station)
        self.station = response.name
        self.x = response.x
        self.y = response.y
        self._simulation.schedule(eta, 'arrive_at_sink')

    def arrive_at_sink(self):
        self._simulation.schedule(self.unload, 'drop_part')

    def drop_part(self):
        with self._channel(self.station) as channel:
            stub = simulation_pb2_grpc.SinkStub(channel)
            response = stub.put_part(Empty())

        logger.info("part droped at %s", self.station)

        if response.time:
            # station full -> wait
            self._simulation.schedule(response.time, 'drop_part')
        else:

            # call all sources and select oldest order (fifo)
            times = {}
            for source in self.sources:
                try:
                    with self._channel(source) as channel:
                        stub = simulation_pb2_grpc.SourceStub(channel)
                        response = stub.next_order(Empty())
                        times[source] = response.time
                except grpc.RpcError as e:
                    logger.info(str(e))

            logger.debug("valid sources: %s", times)

            # select nearest vehicle first
            if times:
                source = min(times, key=times.get)

                with self._channel(source) as channel:
                    stub = simulation_pb2_grpc.SourceStub(channel)
                    response = stub.reserve_next(Empty())

                logger.info("driving to %s", source)

                eta = self.get_eta(response.x, response.y)
                self.station = source
                self.x = response.x
                self.y = response.y

                # schedule next part generation
                self._simulation.schedule(eta, 'arrive_at_source')
            else:
                self.idle = True


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.INFO))
    run = Vehicle()
    run()

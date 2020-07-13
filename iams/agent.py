#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from queue import Queue

import grpc
import yaml

from google.protobuf.empty_pb2 import Empty

from .proto import agent_pb2
from .proto import agent_pb2_grpc
from .proto import framework_pb2
from .stub import AgentStub
from .stub import FrameworkStub
from .utils.auth import permissions
from .utils.grpc import framework_channel


logger = logging.getLogger(__name__)


AgentData = framework_pb2.AgentData


class Servicer(agent_pb2_grpc.AgentServicer):

    def __init__(self, parent, threadpool):
        self.address = os.environ.get('IAMS_ADDRESS', None)
        self.agent = os.environ.get('IAMS_AGENT', None)
        self.config = os.environ.get('IAMS_CONFIG', None)
        self.port = os.environ.get('IAMS_PORT', None)
        self.service = os.environ.get('IAMS_SERVICE', None)
        self.simulation = os.environ.get('IAMS_SIMULATION', None) == "true"
        self.cloud = not os.environ.get('IAMS_CLOUDLESS', None) == "true"

        if self.cloud:
            assert self.agent is not None, 'Must define IAMS_AGENT in environment'
            assert self.service is not None, 'Must define IAMS_SERVICE in environment'
            self.prefix = self.agent.split('_')[0]
        else:
            self.prefix = ""

        self.parent = parent
        self.queue = None
        self.threadpool = threadpool

        # topology cache
        self._topology = None

    @permissions(has_groups=["root"])
    def run_simulation(self, request, context):
        if not self.simulation:
            message = 'This function is only availabe when agenttype is set to simulation'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

        logger.debug("run simulation called")

        self.queue = Queue()
        self.parent._simulation.set_event(request.uuid, request.time)

        while True:
            data = self.queue.get()
            logger.debug("found %s in queue", type(data))
            if isinstance(data, agent_pb2.SimulationLog):
                yield agent_pb2.SimulationResponse(log=data)
            elif isinstance(data, agent_pb2.SimulationMetric):
                yield agent_pb2.SimulationResponse(metric=data)
            elif isinstance(data, agent_pb2.SimulationSchedule):
                yield agent_pb2.SimulationResponse(schedule=data)
            elif isinstance(data, agent_pb2.SimulationResponse):
                yield data
            else:
                break
        self.queue = None

    # TODO unused?
    @permissions(has_agent=True)
    def topology(self, request, context):
        nodes, edges = self.parent.topology()
        return agent_pb2.Topology(name=self.agent, nodes=nodes, edges=edges)

    @permissions(has_agent=True, has_groups=["root"])
    def ping(self, request, context):
        return Empty()

    # === calls to iams =======================================================

    def get_agents(self, labels=[]) -> list:
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = FrameworkStub(channel)
                for response in stub.agents(framework_pb2.AgentRequest(filter=labels), timeout=10):
                    yield response
        except grpc.RpcError:
            raise StopIteration

    def call_booted(self) -> bool:
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = FrameworkStub(channel)
                stub.booted(Empty(), timeout=10)
            return True
        except grpc.RpcError:
            return False

    def call_create(self, name, image, version="latest", config={}) -> (bool, object):
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = FrameworkStub(channel)
                response = stub.create(AgentData(
                    name=name,
                    image=image,
                    version=version,
                    config=yaml.dump(config).encode('utf-8'),
                    autostart=True,
                ), timeout=10)
            return True, response
        except grpc.RpcError as e:
            logger.debug(e, exc_info=True)
            return False, e.code()

    def call_destroy(self) -> bool:
        try:
            with framework_channel() as channel:
                stub = FrameworkStub(channel)
                stub.booted(Empty(), timeout=10)
            return True
        except grpc.RpcError:
            return False

    def call_renew(self, hard=True) -> bool:
        try:
            with framework_channel() as channel:
                stub = FrameworkStub(channel)
                response = stub.renew(framework_pb2.RenewRequest(hard=hard), timeout=10)
            return response.private_key, response.certificate
        except grpc.RpcError:
            return False

    def call_sleep(self) -> bool:
        try:
            with framework_channel() as channel:
                stub = FrameworkStub(channel)
                stub.sleep(Empty(), timeout=10)
            return True
        except grpc.RpcError:
            return False

    def call_upgrade(self) -> bool:
        try:
            with framework_channel() as channel:
                stub = FrameworkStub(channel)
                stub.upgrade(Empty(), timeout=10)
            return True
        except grpc.RpcError:
            return False

    def call_wake(self, agent) -> bool:
        try:
            with framework_channel() as channel:
                stub = FrameworkStub(channel)
                stub.wake(framework_pb2.WakeAgent(agent=agent), timeout=10)
            return True
        except grpc.RpcError:
            return False

    def call_ping(self, agent):
        try:
            with framework_channel(agent) as channel:
                stub = AgentStub(channel)
                stub.ping(Empty(), timeout=10)
            logger.debug("Ping response (%s)", agent)
            return True
        except grpc.RpcError as e:
            logger.debug("Ping response %s: %s from %s", e.code(), e.details(), agent)
            return False

    def update_topology(self, node) -> bool:
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = FrameworkStub(channel)
                self._topology = stub.topology(node, timeout=10)
            return True
        except grpc.RpcError:
            return False


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

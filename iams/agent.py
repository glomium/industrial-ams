#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

import grpc

from google.protobuf.empty_pb2 import Empty

from .proto import agent_pb2_grpc
from .proto import framework_pb2
from .proto import framework_pb2_grpc
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

        assert self.agent is not None, 'Must define AMS_AGENT in environment'
        assert self.service is not None, 'Must define AMS_CORE in environment'

        self.parent = parent
        self.threadpool = threadpool

    @permissions(has_groups=["root"])
    def resume_simulation(self, request, context):
        if not self.simulation:
            message = 'This function is only availabe when agenttype is set to simulation'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

        logger.debug("resume_simulation called")
        self.parent._simulation.set_event(request.uuid, request.time)
        return Empty()

    @permissions(has_agent=True, has_groups=["root"])
    def ping(self, request, context):
        return Empty()

    # === calls to iams =======================================================

    def get_agents(self, labels=[]) -> list:
        try:
            with framework_channel(credentials=self.parent._credentials) as channel:
                stub = FrameworkStub(channel)
                for response in stub.agents(framework_pb2_grpc.AgentRequest(filter=labels), timeout=10):
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


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

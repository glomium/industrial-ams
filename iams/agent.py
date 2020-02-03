#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

# from uuid import uuid1

import grpc
# import msgpack

from google.protobuf.empty_pb2 import Empty

from .proto import agent_pb2_grpc
# from .proto import framework_pb2_grpc
from .proto import framework_pb2
# from .proto import simulation_pb2_grpc
# from .proto.agent_pb2 import ConnectionResponse
# from .proto.agent_pb2 import PingResponse
# from .proto.agent_pb2 import ServiceResponse
# from .proto.framework_pb2 import WakeAgent
# from .proto.simulation_pb2 import EventRegister
from .stub import FrameworkStub
from .utils.auth import permissions
from .utils.grpc import framework_channel
# from .utils.grpc import grpc_retry


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
    def resume(self, request, context):
        if not self.simulation:
            message = 'This function is only availabe when agenttype is set to simulation'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        logger.debug("simulation_continue called")
        self.parent._simulation.event_trigger(request.uuid, request.time)
        return Empty()

    # @permissions(has_agent=True, has_groups=["root"])
    # def ping(self, request, context):
    #     return Empty()

    def call_booted(self) -> bool:
        with framework_channel() as channel:
            stub = FrameworkStub(channel)
            stub.booted(Empty(), timeout=10)
        return True

    # def call_destroy(self) -> bool:
    #     logger.debug("calling AMS to be killed")
    #     with framework_channel() as channel:
    #         stub = FrameworkStub(channel)
    #         stub.destroy(Empty(), timeout=10)
    #     return True
    # def call_sleep(self) -> bool:
    #     logger.debug("calling AMS to be sent to sleep")
    #     with framework_channel() as channel:
    #         stub = FrameworkStub(channel)
    #         stub.sleep(Empty(), timeout=10)
    #     return True
    # def call_upgrade(self) -> bool:
    #     with framework_channel() as channel:
    #         stub = FrameworkStub(channel)
    #         stub.upgrade(Empty(), timeout=10)
    #     return True
    # def call_wake(self, other) -> bool:
    #     with framework_channel() as channel:
    #         stub = FrameworkStub(channel)
    #         stub.upgrade(WakeAgent(agent=other), timeout=10)
    #     return True

    # self.validate_connection

#   def agent_ping(self, agent):
#       try:
#           with framework_channel(agent) as channel:
#               stub = AgentStub(channel)
#               response = stub.ping(Empty(), timeout=10)
#           logger.debug("Ping response (%s) %s:%s", agent, response.image, response.version)
#           return True
#       except grpc.RpcError as e:
#           logger.debug("Ping response %s: %s from %s", e.code(), e.details(), agent)
#           return False

#   # def simulation_resume(self, delay=None) -> bool:
#   #     if self.simulation is None:
#   #         return False
#   #     logger.error("Deprecation!!")
#   #     if delay is None:
#   #         request = EventRegister()
#   #     else:
#   #         request = EventRegister(uuid=uuid1().bytes, delay=delay)
#   #     try:
#   #         with framework_channel() as channel:
#   #             stub = SimulationStub(channel)
#   #             stub.resume(request, timeout=10)
#   #         if delay is not None:
#   #             logger.debug("continue with execution in %s seconds", delay)
#   #         return True
#   #     except grpc.RpcError as e:
#   #         logger.exception("error %s in simulation_resume: %s", e.code(), e.details())
#   #         return False


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

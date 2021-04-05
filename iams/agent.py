#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams agent
"""

import logging
import os

import grpc
# import yaml

from google.protobuf.empty_pb2 import Empty

# from iams.proto import agent_pb2
from iams.proto import agent_pb2_grpc
from iams.proto import framework_pb2
# from iams.stub import AgentStub
# from iams.stub import FrameworkStub
from iams.utils.grpc import credentials


logger = logging.getLogger(__name__)


AgentData = framework_pb2.AgentData


class Servicer(agent_pb2_grpc.AgentServicer):  # pylint: disable=too-many-instance-attributes,empty-docstring

    def __init__(self, parent, threadpool):
        self.address = os.environ.get('IAMS_ADDRESS', None)
        self.agent = os.environ.get('IAMS_AGENT', None)
        self.config = os.environ.get('IAMS_CONFIG', None)
        self.port = os.environ.get('IAMS_PORT', None)
        self.service = os.environ.get('IAMS_SERVICE', None)
        self.cloud = not os.environ.get('IAMS_CLOUDLESS', None) == "true"

        if self.cloud:
            assert self.agent is not None, 'Must define IAMS_AGENT in environment'
            assert self.service is not None, 'Must define IAMS_SERVICE in environment'
            self.prefix = self.agent.split('_')[0]
        else:
            self.prefix = ""

        self.parent = parent
        self.position = None
        self.queue = None
        self.threadpool = threadpool

        # caches
        self._topology = None

    @credentials
    def ping(self, request, context):
        return Empty()

    @credentials
    def upgrade(self, request, context):
        if self.parent.callback_agent_upgrade():
            return Empty()
        message = 'Upgrade is not allowed'
        return context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @credentials
    def update(self, request, context):
        if self.parent.callback_agent_update():
            return Empty()
        message = 'Update is not allowed'
        return context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @credentials
    def reset(self, request, context):
        if self.parent.callback_agent_reset():
            return Empty()
        message = 'Reset is not allowed'
        return context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @credentials
    def position(self, request, context):
        if self.update_position(context.credentials):  # pylint: disable=protected-access
            return Empty()
        message = 'Agent is already at requested position'
        return context.abort(grpc.StatusCode.ALREADY_EXISTS, message)

    # === calls to iams =======================================================

    def update_position(self, position) -> bool:
        """
        update position
        """
        if self.position == position:
            return False

        self.position = position
        # TODO: position update callback on previous position
        return True

    # def call_booted(self) -> bool:
    #     """
    #     call booted
    #     """
    #     try:
    #         # pylint: disable=protected-access
    #         with framework_channel(credentials=self.parent._credentials) as channel:
    #             stub = FrameworkStub(channel)
    #             stub.booted(Empty(), timeout=10)
    #         return True
    #     except grpc.RpcError:
    #         return False

    # def call_create(self, name, image, version="latest", config=None) -> (bool, object):
    #     """
    #     call create
    #     """
    #     try:
    #         # pylint: disable=protected-access
    #         with framework_channel(credentials=self.parent._credentials) as channel:
    #             stub = FrameworkStub(channel)
    #             response = stub.create(AgentData(
    #                 name=name,
    #                 image=image,
    #                 version=version,
    #                 config=yaml.dump(config or {}).encode('utf-8'),
    #                 autostart=True,
    #             ), timeout=10)
    #         return True, response
    #     except grpc.RpcError as exception:
    #         logger.debug(exception, exc_info=True)
    #         return False, exception.code()  # pylint: disable=no-member

    # @staticmethod
    # def call_destroy() -> bool:
    #     """
    #     call destroy
    #     """
    #     try:
    #         with framework_channel() as channel:
    #             stub = FrameworkStub(channel)
    #             stub.booted(Empty(), timeout=10)
    #         return True
    #     except grpc.RpcError:
    #         return False

    # @staticmethod
    # def call_renew(hard=True) -> bool:
    #     """
    #     call renew
    #     """
    #     try:
    #         with framework_channel() as channel:
    #             stub = FrameworkStub(channel)
    #             response = stub.renew(framework_pb2.RenewRequest(hard=hard), timeout=10)
    #         return response.private_key, response.certificate
    #     except grpc.RpcError:
    #         return False

    # @staticmethod
    # def call_sleep() -> bool:
    #     """
    #     call sleep
    #     """
    #     try:
    #         with framework_channel() as channel:
    #             stub = FrameworkStub(channel)
    #             stub.sleep(Empty(), timeout=10)
    #         return True
    #     except grpc.RpcError:
    #         return False

    # @staticmethod
    # def call_upgrade() -> bool:
    #     """
    #     call upgrade
    #     """
    #     try:
    #         with framework_channel() as channel:
    #             stub = FrameworkStub(channel)
    #             stub.upgrade(Empty(), timeout=10)
    #         return True
    #     except grpc.RpcError:
    #         return False

    # @staticmethod
    # def call_wake(agent) -> bool:
    #     """
    #     call wake
    #     """
    #     try:
    #         with framework_channel() as channel:
    #             stub = FrameworkStub(channel)
    #             stub.wake(framework_pb2.WakeAgent(agent=agent), timeout=10)  # pylint: disable=no-member
    #         return True
    #     except grpc.RpcError:
    #         return False

    # @staticmethod
    # def call_ping(agent):
    #     """
    #     call ping
    #     """
    #     try:
    #         with framework_channel(agent) as channel:
    #             stub = AgentStub(channel)
    #             stub.ping(agent_pb2.PingRequest(), timeout=10)
    #         logger.debug("Ping response (%s)", agent)
    #         return True
    #     except grpc.RpcError as exception:
    #         # pylint: disable=no-member
    #         logger.debug("Ping response %s: %s from %s", exception.code(), exception.details(), agent)
    #         return False

    # @staticmethod
    # def call_update(agent):
    #     """
    #     call update
    #     """
    #     try:
    #         with framework_channel(agent) as channel:
    #             stub = AgentStub(channel)
    #             stub.update(agent_pb2.UpdateRequest(), timeout=10)
    #         logger.debug("Update response (%s)", agent)
    #         return True
    #     except grpc.RpcError as exception:
    #         # pylint: disable=no-member
    #         logger.debug("Update response %s: %s from %s", exception.code(), exception.details(), agent)
    #         return False

    # @staticmethod
    # def call_reset(agent):
    #     """
    #     call reset
    #     """
    #     try:
    #         with framework_channel(agent) as channel:
    #             stub = AgentStub(channel)
    #             stub.reset(agent_pb2.ResetRequest(), timeout=10)
    #         logger.debug("Reset response (%s)", agent)
    #         return True
    #     except grpc.RpcError as exception:
    #         # pylint: disable=no-member
    #         logger.debug("Reset response %s: %s from %s", exception.code(), exception.details(), agent)
    #         return False

    # def update_topology(self, node) -> bool:
    #     """
    #     update topology
    #     """
    #     try:
    #         # pylint: disable=protected-access
    #         with framework_channel(credentials=self.parent._credentials) as channel:
    #             stub = FrameworkStub(channel)
    #             self._topology = stub.topology(node, timeout=10)
    #         return True
    #     except grpc.RpcError:
    #         return False


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

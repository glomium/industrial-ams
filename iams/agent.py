#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os

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

    @permissions(has_agent=True, has_groups=["root", "web"])
    def ping(self, request, context):
        return Empty()

    @permissions(has_agent=True, has_groups=["root", "web"])
    def upgrade(self, request, context):
        if self.parent.callback_agent_upgrade():
            return Empty()
        else:
            message = 'Upgrade is not allowed'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @permissions(has_agent=True, has_groups=["root", "web"])
    def update(self, request, context):
        if self.parent.callback_agent_update():
            return Empty()
        else:
            message = 'Update is not allowed'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @permissions(has_agent=True, has_groups=["root", "web"])
    def reset(self, request, context):
        if self.parent.callback_agent_reset():
            return Empty()
        else:
            message = 'Reset is not allowed'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @permissions(has_agent=True)
    def position(self, request, context):
        if self.update_position(context._agent):
            return Empty()
        message = 'Agent is already at requested position'
        context.abort(grpc.StatusCode.ALREADY_EXISTS, message)

    # === calls to iams =======================================================

    def update_position(self, position) -> bool:
        if self.position == position:
            return False

        self.position = position
        # TODO: position update callback on previous position
        return True

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
                stub.ping(agent_pb2.PingRequest(), timeout=10)
            logger.debug("Ping response (%s)", agent)
            return True
        except grpc.RpcError as e:
            logger.debug("Ping response %s: %s from %s", e.code(), e.details(), agent)
            return False

    def call_update(self, agent):
        try:
            with framework_channel(agent) as channel:
                stub = AgentStub(channel)
                stub.update(agent_pb2.UpdateRequest(), timeout=10)
            logger.debug("Update response (%s)", agent)
            return True
        except grpc.RpcError as e:
            logger.debug("Update response %s: %s from %s", e.code(), e.details(), agent)
            return False

    def call_reset(self, agent):
        try:
            with framework_channel(agent) as channel:
                stub = AgentStub(channel)
                stub.reset(agent_pb2.ResetRequest(), timeout=10)
            logger.debug("Reset response (%s)", agent)
            return True
        except grpc.RpcError as e:
            logger.debug("Reset response %s: %s from %s", e.code(), e.details(), agent)
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

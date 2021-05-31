#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams agent
"""

from concurrent.futures import ThreadPoolExecutor
import logging
import os

import grpc
# import yaml

from google.protobuf.empty_pb2 import Empty

# from iams.proto import agent_pb2
from iams.aio.manager import Manager
from iams.proto import agent_pb2_grpc
from iams.proto import framework_pb2
# from iams.stub import AgentStub
# from iams.stub import FrameworkStub
from iams.utils.grpc import credentials


logger = logging.getLogger(__name__)


AgentData = framework_pb2.AgentData


class AgentBase:
    """
    Base class for agents
    """

    __hash__ = None
    MAX_WORKERS = None

    def __init__(self) -> None:
        self.aio_manager = Manager()

    def __repr__(self):
        return self.__class__.__qualname__ + "()"

    def _pre_setup(self):
        """
        libraries can overwrite this function
        """

    def _post_setup(self):
        """
        libraries can overwrite this function
        """

    def setup(self):
        """
        overwrite this function
        """

    def __call__(self):
        self._pre_setup()
        self.setup()
        self._post_setup()

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            self.aio_manager(executor)


class Servicer(agent_pb2_grpc.AgentServicer):  # pylint: disable=too-many-instance-attributes,empty-docstring

    def __init__(self, parent):
        self.address = os.environ.get('IAMS_ADDRESS', None)
        self.agent = os.environ.get('IAMS_AGENT', None)
        self.config = os.environ.get('IAMS_CONFIG', None)
        self.port = os.environ.get('IAMS_PORT', None)
        self.service = os.environ.get('IAMS_SERVICE', None)

        assert self.agent is not None, 'Must define IAMS_AGENT in environment'
        assert self.service is not None, 'Must define IAMS_SERVICE in environment'
        self.prefix = self.agent.split('_')[0]

        self.parent = parent
        self.position = None
        self.queue = None

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

    # @credentials
    # def position(self, request, context):
    #     if self.update_position(context.credentials):  # pylint: disable=protected-access
    #         return Empty()
    #     message = 'Agent is already at requested position'
    #     return context.abort(grpc.StatusCode.ALREADY_EXISTS, message)


class Agent(AgentBase):
    """
    Iams Agent Class
    """


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

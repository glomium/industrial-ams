#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams agent interface definition
"""

# import asyncio
import logging
# import sys

from abc import ABC
# from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor

import grpc
import yaml

from iams.aio.manager import Manager
from iams.agent import Servicer
from iams.proto import ca_pb2
# from iams.proto import df_pb2
from iams.stub import CAStub
# from iams.stub import DFStub
from iams.utils.grpc import Grpc
# from iams.utils.grpc import framework_channel
# from iams.utils.grpc import get_channel_credentials
# from iams.utils.grpc import get_server_credentials
# from iams.utils.ssl import validate_certificate
from iams.proto.agent_pb2_grpc import add_AgentServicer_to_server


logger = logging.getLogger(__name__)


class AgentCAMixin:
    """
    Adds functionality to the agent to interact with certificate authorities
    """

    async def ca_renew(self, hard=True):
        """
        Ask CA for a new certificate
        """
        try:
            with self.grpc.channel as channel:
                stub = CAStub(channel)
                response = await stub.renew(ca_pb2.RenewRequest(hard=hard), timeout=10)  # pylint: disable=no-member
            return response.private_key, response.certificate
        except grpc.RpcError:
            return None, None


class AgentDFMixin:
    """
    Adds functionality to the agent to interact with directory facilitators
    """


class Agent(ABC, AgentCAMixin, AgentDFMixin):  # pylint: disable=too-many-instance-attributes
    """
    iams agents
    """
    __hash__ = None
    MAX_WORKERS = None

    def __init__(self) -> None:
        self.task_manager = Manager()
        self.iams = Servicer(self)
        self.grpc = Grpc(self.iams.agent)

        # agent servicer for iams
        self.grpc.add(add_AgentServicer_to_server, self.iams)

        # TODO make config configureable via environment variable
        try:
            with open('/config', 'rb') as fobj:
                self._config = yaml.load(fobj, Loader=yaml.SafeLoader)
            logger.debug('Loaded configuration from /config')
        except FileNotFoundError:
            logger.debug('Configuration at /config was not found')
            self._config = {}

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
        """
        """
        self._pre_setup()
        self.setup()
        self._post_setup()

        self.task_manager.register(self.grpc)
        with ThreadPoolExecutor(max_workers=1) as executor:
            self.task_manager(executor)

    async def callback_agent_upgrade(self):
        """
        This function can be called from the agents and services to suggest
        hat the agent should upgrate it's software (i.e. docker image)
        """

    async def callback_agent_update(self):
        """
        This function can be called from the agents and services to suggest
        that the agent should update its configuration or state
        """

    async def callback_agent_reset(self):
        """
        This function can be called from the agents and services to suggest
        that the agent should reset its connected device
        """

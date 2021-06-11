#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams agent
"""

from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import logging
import os

import grpc
import yaml

from google.protobuf.empty_pb2 import Empty

# from iams.proto import agent_pb2
from iams.aio.manager import Manager
from iams.proto import agent_pb2_grpc
from iams.proto import framework_pb2
# from iams.stub import AgentStub
# from iams.stub import FrameworkStub


logger = logging.getLogger(__name__)
AgentData = framework_pb2.AgentData


class Context:
    """
    wrapper for grpc context
    """
    def __init__(self, client, identities):
        self.client = client
        self.credetials = identities

    async def abort(self, *args, **kwargs):
        """
        wrapper for grpc context abort
        """
        return await self.client.abort(*args, **kwargs)


def credentials(function):
    """
    credentials decorator (adds a "credentials" attribute to the grpc-context)
    """
    def decorator(func):
        @wraps(func)
        async def wrapped(self, request, context=None):

            # internal request - can be used in unittests
            if context is None:
                logger.debug("Process request as it already as a credentials attribute (internal request)")
                return await func(self, request, Context(context, set()))

            # assign peer identities
            ignore = set([b'127.0.0.1', b'localhost'])
            try:
                identities = set(x.decode('utf-8') for x in context.peer_identities() if x not in ignore)
            except TypeError:
                logger.debug("Could not assign the 'credentials' attribute")
            else:
                return await func(self, request, Context(context, identities))

            # abort unauthentifcated call
            message = "Client needs to be authentifacted"
            logger.debug(message)
            return await context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        return wrapped
    return decorator(function)


class AgentBase:
    """
    Base class for agents
    """
    __hash__ = None
    MAX_WORKERS = None

    def __init__(self) -> None:
        self.aio_manager = Manager()
        self.iams = Servicer(self)

    def __repr__(self):
        return self.__class__.__qualname__ + "()"

    def _setup(self):
        """
        libraries can overwrite this function
        """

    def __call__(self):
        self._setup()

        if hasattr(self, 'grpc'):
            # pylint: disable=no-member
            self.grpc.manager = self.iams.service
            logger.debug("Adding agent servicer to grpc")
            self.grpc.add(agent_pb2_grpc.add_AgentServicer_to_server, self.iams)

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            logger.debug("Starting execution")
            self.aio_manager(self, executor)
            logger.debug("Clearing threadpool")
            executor._threads.clear()
            logger.debug("Shutdown")
            executor.shutdown(wait=False)
            logger.debug("SystemExit")
            raise SystemExit(0)

    async def setup(self, executor):
        """
        overwrite this function
        """

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
    async def ping(self, request, context):  # pylint: disable=invalid-overridden-method
        return Empty()

    @credentials
    async def upgrade(self, request, context):  # pylint: disable=invalid-overridden-method
        if await self.parent.callback_agent_upgrade():
            return Empty()
        message = 'Upgrade is not allowed'
        return await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @credentials
    async def update(self, request, context):  # pylint: disable=invalid-overridden-method
        if await self.parent.callback_agent_update():
            return Empty()
        message = 'Update is not allowed'
        return await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    @credentials
    async def reset(self, request, context):  # pylint: disable=invalid-overridden-method
        if await self.parent.callback_agent_reset():
            return Empty()
        message = 'Reset is not allowed'
        return await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)


class Agent(AgentBase):
    """
    Iams Agent Class
    """
    def __init__(self) -> None:
        super().__init__()
        # TODO make config configureable via environment variable
        try:
            with open('/config', 'rb') as fobj:
                self._config = yaml.load(fobj, Loader=yaml.SafeLoader)
            logger.debug('Loaded configuration from /config')
        except FileNotFoundError:
            logger.debug('Configuration at /config was not found')
            self._config = {}


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

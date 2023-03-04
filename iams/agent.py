#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams agent
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
# from signal import SIGKILL

import grpc
import yaml

from google.protobuf.empty_pb2 import Empty  # pylint: disable=no-name-in-module

# from iams.proto import agent_pb2
from iams.aio.manager import Manager
from iams.proto import agent_pb2_grpc
from iams.proto import framework_pb2
# from iams.stub import AgentStub
# from iams.stub import FrameworkStub


logger = logging.getLogger(__name__)
AgentData = framework_pb2.AgentData  # pylint: disable=no-member


async def credentials(context, optional=False):
    """
    credentials decorator (adds a "credentials" attribute to the grpc-context)
    """
    # internal request - can be used in unittests
    if context is None:
        logger.debug("Process request as it already as a credentials attribute (internal request)")
        return set()

    # assign peer identities
    ignore = set([b'127.0.0.1', b'localhost'])
    try:
        return set(x.decode('utf-8') for x in context.peer_identities() if x and x not in ignore)
    except TypeError:
        logger.debug("Could not assign the 'credentials' attribute")

    if optional:
        return set()

    # abort unauthentifcated call
    message = "Client needs to be authentifacted"
    logger.debug(message)
    await context.abort(grpc.StatusCode.UNAUTHENTICATED, message)


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

        pidfile = Path("/run/iams_agent.pid")
        executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        try:
            try:
                with pidfile.open("w", encoding="ASCII") as fobj:
                    fobj.write(str(os.getpid()))
                logger.debug("Created pidfile %s", pidfile)
            except OSError:
                logger.debug("Could not create pidfile %s", pidfile)

            logger.debug("Starting execution")
            self.aio_manager(self, executor)
        finally:
            if pidfile.exists():
                try:
                    pidfile.unlink()
                    logger.debug("Removed pidfile %s", pidfile)
                except OSError:
                    logger.debug("Could not remove pidfile %s", pidfile)

            logger.debug("Shutdown ...")
            executor.shutdown(wait=False)
            logger.debug("Sending SIGKILL to kill all processes")

            # force exit via os.kill
            # os.kill(os.getppid(), SIGKILL)
            # os.kill(os.getpid(), SIGKILL)

    async def setup(self, executor):
        """
        overwrite this function
        """

    async def callback_agent_authenticate(self, identities, context):
        """
        This function should return True if the agent calling is authenticated
        to access the agent servicer
        """

    async def callback_agent_upgrade(self, identities, context):
        """
        This function can be called from the agents and services to suggest
        hat the agent should upgrate it's software (i.e. docker image)
        """

    async def callback_agent_update(self, identities, context):
        """
        This function can be called from the agents and services to suggest
        that the agent should update its configuration or state
        """

    async def callback_agent_reset(self, identities, context):
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
        self.prefix = self.agent.split('_', 1)[0] + '_'
        self.parent = parent

    async def online(self, request, context):  # pylint: disable=invalid-overridden-method
        identities = await credentials(context)
        if not await self.parent.callback_agent_authenticate(identities, context):
            message = 'Not allowed to access'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        while True:
            yield Empty()
            await asyncio.sleep(300)

    async def ping(self, request, context):  # pylint: disable=invalid-overridden-method
        identities = await credentials(context)
        if not await self.parent.callback_agent_authenticate(identities, context):
            message = 'Not allowed to access'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        return Empty()

    async def reset(self, request, context):  # pylint: disable=invalid-overridden-method
        identities = await credentials(context)
        if not await self.parent.callback_agent_authenticate(identities, context):
            message = 'Not allowed to access'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        if not await self.parent.callback_agent_reset(identities, context):
            message = 'Reset is not allowed'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        return Empty()

    async def update(self, request, context):  # pylint: disable=invalid-overridden-method
        identities = await credentials(context)
        if not await self.parent.callback_agent_authenticate(identities, context):
            message = 'Not allowed to access'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        if not await self.parent.callback_agent_update(identities, context):
            message = 'Update is not allowed'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        return Empty()

    async def upgrade(self, request, context):  # pylint: disable=invalid-overridden-method
        identities = await credentials(context)
        if not await self.parent.callback_agent_authenticate(identities, context):
            message = 'Not allowed to access'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        if not await self.parent.callback_agent_upgrade(identities, context):
            message = 'Upgrade is not allowed'
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        return Empty()


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

    async def callback_agent_authenticate(self, identities, context):
        return True


Servicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

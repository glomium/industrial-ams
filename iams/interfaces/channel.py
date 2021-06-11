#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Channel context manager
"""

import logging

from abc import ABC

import grpc

from google.protobuf.empty_pb2 import Empty

from iams.constants import AGENT_PORT
from iams.stub import AgentStub


logger = logging.getLogger(__name__)


class Channel(ABC):
    """
    Channel Interface
    """
    __hash__ = None

    def __init__(self, parent, agent) -> None:
        self._agent = agent
        self._state = None
        self._channel = grpc.secure_channel(f'{agent!s}:{AGENT_PORT!s}', parent._credentials)
        self._parent = parent
        self._channel.subscribe(self._set_state, try_to_connect=True)

    def __enter__(self):
        return self._channel

    def __exit__(self, exception_type, exception_value, traceback):
        return None

    def _set_state(self, connectivity):
        logger.debug("ChannelConnectivity to %s changed to %s", self._agent, connectivity)
        if connectivity == grpc.ChannelConnectivity.IDLE:
            try:
                # if the channel is idle and no request was exchanged, we ping the agent to get a
                # force the change of the connection
                AgentStub(self._channel).ping(Empty())
            except grpc.RpcError as exception:
                # pylint: disable=no-member
                logger.info("Ping to %s failed: %s", self._agent, exception.details())
        elif connectivity == grpc.ChannelConnectivity.READY:
            self.connected(self._parent)
        elif self._state == grpc.ChannelConnectivity.READY:
            self.disconnected(self._parent)

        self._state = connectivity

    def connected(self, parent):
        """
        connected
        """

    def disconnected(self, parent):
        """
        disconnected
        """

    def __bool__(self):
        return self._state == grpc.ChannelConnectivity.READY

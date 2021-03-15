#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from abc import ABC
from abc import abstractmethod

import grpc

from google.protobuf.empty_pb2 import Empty

from ..constants import AGENT_CLOUDLESS
from ..constants import AGENT_PORT
from ..stub import AgentStub


logger = logging.getLogger(__name__)


class Channel(ABC):
    __hash__ = None

    def __init__(self, parent, agent) -> None:
        self._agent = agent
        self._state = None
        if parent._iams.cloud:
            port = AGENT_PORT
            self._channel = grpc.secure_channel(f'{agent!s}:{port!s}', parent._credentials)
        else:
            port = AGENT_CLOUDLESS
            self._channel = grpc.insecure_channel(f'{agent!s}:{port!s}')
        self._parent = parent
        self._channel.subscribe(self._set_state, try_to_connect=True)

    def __enter__(self):
        return self._channel

    def __exit__(self):
        return None

    def _set_state(self, connectivity):
        logger.debug("ChannelConnectivity to %s changed to %s", self._agent, connectivity)
        if connectivity == grpc.ChannelConnectivity.IDLE:
            try:
                # if the channel is idle and no request was exchanged, we ping the agent to get a
                # force the change of the connection
                AgentStub(self._channel).ping(Empty())
            except grpc.RpcError as e:
                logger.info("Ping to %s failed: %s", self._agent, e.details())
        elif connectivity == grpc.ChannelConnectivity.READY:
            self.connected(self._parent)
        elif self._state == grpc.ChannelConnectivity.READY:
            self.disconnected(self._parent)

        self._state = connectivity

    def connected(self, parent):
        pass

    def disconnected(self, parent):
        pass

    def __bool__(self):
        return self._state == grpc.ChannelConnectivity.READY


class Plugin(ABC):

    __hash__ = None

    def __init__(self, namespace, simulation):
        self.namespace = namespace
        self.simulation = simulation

    def __repr__(self):
        return self.__class__.__qualname__ + "()"

    def __call__(self, name, image, version, config):
        kwargs = self.get_kwargs(name, image, version, config)

        return (
            self.get_env(**kwargs),
            self.get_labels(**kwargs),
            set(self.get_networks(**kwargs)),
            self.get_configured_secrets(**kwargs),
            self.get_generated_secrets(**kwargs),
        )

    @classmethod
    @abstractmethod
    def label(cls):  # pragma: no cover
        pass

    def remove(self, name, config):
        """
        called when agent is removed
        """
        pass

    def get_kwargs(self, name, image, version, config):
        """
        generate keyword arguements
        """
        return {}

    def get_labels(self, **kwargs):
        """
        set labels for agent
        """
        return {}

    def get_env(self, **kwargs):
        """
        set enviromment variables for agent
        """
        return {}

    def get_networks(self, **kwargs):
        """
        add agent to networks
        """
        return []

    def get_configured_secrets(self, **kwargs):
        """
        add preconfigured secret to agent
        """
        return {}

    def get_generated_secrets(self, **kwargs):
        """
        add automatically generated secret to agent
        """
        return []

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams agent interface definition
"""

import logging
import signal
import sys

from abc import ABC
from abc import abstractmethod
from concurrent import futures
from contextlib import contextmanager
from threading import Event
from threading import Lock
from time import sleep

import grpc
import yaml

from iams.agent import Servicer
from iams.proto import ca_pb2
# from iams.proto import df_pb2
from iams.stub import CAStub
# from iams.stub import DFStub
from iams.utils.grpc import Grpc
from iams.utils.grpc import framework_channel
from iams.utils.grpc import get_channel_credentials
from iams.utils.grpc import get_server_credentials
from iams.utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class AgentCAMixin:
    """
    Adds functionality to the agent to interact with certificate authorities
    """

    @staticmethod
    def ca_renew(hard=True):
        """
        Ask CA for a new certificate
        """
        try:
            with framework_channel() as channel:
                stub = CAStub(channel)
                response = stub.renew(ca_pb2.RenewRequest(hard=hard), timeout=10)  # pylint: disable=no-member
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
        self._executor = futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        # agent servicer for iams
        self._iams = Servicer(self, self._executor)

        if self._iams.cloud:
            self._credentials = get_channel_credentials()
            # grpc communication (via threadpoolexecutor)
            self._grpc = Grpc(self._iams, self._executor, get_server_credentials())
            try:
                with open('/config', 'rb') as fobj:
                    self._config = yaml.load(fobj, Loader=yaml.SafeLoader)
                logger.debug('Loaded configuration from /config')

            except FileNotFoundError:
                logger.debug('Configuration at /config was not found')
                self._config = {}
        else:
            self._credentials = None
            self._grpc = Grpc(self._iams, self._executor, None)
            self._config = {}

        self._lock = Lock()
        self._loop_event = Event()
        self._stop_event = Event()

        # create signals to catch sigterm events
        signal.signal(signal.SIGINT, self.__stop)
        signal.signal(signal.SIGTERM, self.__stop)

    def __repr__(self):
        return self.__class__.__qualname__ + "()"

    def __call__(self):
        # run setup methods for controlling machines
        self._pre_setup()
        self.setup()
        self._post_setup()

        # load and start gRPC service
        self.grpc_setup()  # local module specification
        self._grpc_setup()  # definition on mixins
        self._grpc.start()

        if self._iams.cloud:
            logger.debug("Informing the runtime that %s is booted", self._iams.agent)
            while not self._stop_event.is_set():
                if self._iams.call_booted():
                    break
                if not validate_certificate():
                    if self.ca_renew():
                        logger.info("Certificate needs to be renewed")
                        sleep(600)
                    else:
                        logger.debug("Could not connect to manager")
                        sleep(1)

        # run agent configuration
        try:
            self.configure()  # local module specification
            self._configure()  # definitions on mixins
        except grpc.RpcError as exception:  # pragma: no cover
            # pylint: disable=no-member
            logger.debug(
                "gRPC request failed in configure - resetting: %s - %s",
                exception.code(),
                exception.details(),
            )
            sys.exit()

        if not self._stop_event.is_set():
            # control loop
            logger.debug("Calling control loop")
            self._start()
            self.start()
            try:
                self._loop()
            except Exception as exception:  # pylint: disable=broad-except # pragma: no cover
                logger.exception(str(exception))

        logger.debug("Stopping gRPC service on %s", self._iams.agent)
        self._grpc.stop()

        logger.debug("call self.teardown")
        self.teardown()
        logger.debug("call self._teardown")
        self._teardown()

        logger.info("Exit %s", self._iams.agent)
        sys.exit()

    def __stop(self, signum, frame):
        logger.info("Exit requested with code %s (%s)", signum, frame)
        self.stop()

    @contextmanager
    def _channel(self, agent=None):
        with framework_channel(hostname=agent, credentials=self._credentials) as channel:
            yield channel

    def _grpc_setup(self):
        """
        this method can be overwritten by mixins
        """

    def _pre_setup(self):
        """
        this method can be overwritten by mixins
        """

    def _post_setup(self):
        """
        this method can be overwritten by mixins
        """

    def _start(self):
        """
        this method can be overwritten by mixins
        """

    def _teardown(self):
        """
        this method can be overwritten by mixins
        """

    @abstractmethod
    def _loop(self):
        """
        this method can be overwritten by mixins
        """

    def _configure(self):
        """
        this method can be overwritten by mixins
        """

    def configure(self):
        """
        configure is called after the agent informed the AMS that its booted. this step can be used to load
        additional information into the agent
        """

    def setup(self):
        """
        executed directly after the instance is called. user defined.
        idea: setup communication to machine
        """

    def grpc_setup(self):
        """
        add user-defined servicers to the grpc server
        """

    def start(self):
        """
        executed directly before the loop runs
        execute functions that require the connection to other agents here.
        """

    def stop(self):
        """
        stops the container
        """
        self._stop_event.set()
        self._loop_event.set()

    def teardown(self):
        """
        function that might be used to inform other agents or services that this agent is
        about to shutdown
        """

    def callback_agent_upgrade(self):
        """
        This function can be called from the agents and services to suggest
        hat the agent should upgrate it's software (i.e. docker image)
        """

    def callback_agent_update(self):
        """
        This function can be called from the agents and services to suggest
        that the agent should update its configuration or state
        """

    def callback_agent_reset(self):
        """
        This function can be called from the agents and services to suggest
        that the agent should reset its connected device
        """

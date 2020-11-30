#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import signal

from abc import ABC
from abc import abstractmethod
from concurrent import futures
from contextlib import contextmanager
from threading import Event
from threading import Lock
from time import sleep

import grpc
import yaml

from ..agent import Servicer
from ..exceptions import Continue
from ..exceptions import EventNotFound
from ..scheduler import Scheduler
from ..utils.grpc import Grpc
from ..utils.grpc import framework_channel
from ..utils.grpc import get_channel_credentials
from ..utils.grpc import get_server_credentials
from ..utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class Agent(ABC):
    """
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

        if self._iams.simulation:
            self._simulation = Scheduler(self, self._iams)
        else:
            self._simulation = None

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
        if not self._iams.simulation:
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
                    if self._iams.call_renew():
                        logger.info("Certificate needs to be renewed")
                        sleep(600)
                    else:
                        logger.debug("Could not connect to manager")
                        sleep(1)

        # run agent configuration
        try:
            self.configure()  # local module specification
            self._configure()  # definitions on mixins
        except grpc.RpcError as e:  # pragma: no cover
            logger.debug("gRPC request failed in configure - resetting: %s - %s", e.code(), e.details())
            exit()

        if self._iams.simulation:
            started = False
            # simulation loop
            while True:
                # wait for event loop
                logger.debug("waiting for wakeup event")
                self._loop_event.wait()
                self._loop_event.clear()

                # if agent should be stopped discontinue execution
                if self._stop_event.is_set():
                    break

                if not started:
                    self._start()
                    self.start()
                    started = True

                try:
                    callback, kwargs = next(self._simulation)
                except EventNotFound:
                    logger.debug("Skip execution of next step - scheduled event was not found")
                    self._simulation.resume()
                    continue

                # execute callbacks (event based simulation)
                logger.debug("calling %s.%s with %s", self.__class__.__qualname__, callback, kwargs)
                try:
                    getattr(self, callback)(**kwargs)
                except Continue:
                    pass

                logger.debug("calling resume")
                self._simulation.resume()

        elif not self._stop_event.is_set():
            # control loop
            logger.debug("Calling control loop")
            self._start()
            self.start()
            try:
                self._loop()
            except Exception as e:
                logger.exception(e)

        logger.debug("Stopping gRPC service on %s", self._iams.agent)
        self._grpc.stop()

        if not self._iams.simulation:
            self.teardown()
            self._teardown()

        logger.info("Exit %s", self._iams.agent)
        exit()

    def __stop(self, signum, frame):
        logger.info("Exit requested with code %s", signum)
        self.stop()

    @contextmanager
    def _channel(self, agent=None):
        with framework_channel(hostname=agent, credentials=self._credentials) as channel:
            yield channel

    def _grpc_setup(self):
        """
        this method can be overwritten by mixins
        """
        pass

    def _pre_setup(self):
        """
        this method can be overwritten by mixins
        """
        pass

    def _post_setup(self):
        """
        this method can be overwritten by mixins
        """
        pass

    def _start(self):
        """
        this method can be overwritten by mixins
        """
        pass

    def _teardown(self):
        """
        this method can be overwritten by mixins
        """
        pass

    @abstractmethod
    def _loop(self):  # pragma: no cover
        """
        this method can be overwritten by mixins
        """
        pass

    def _configure(self):
        """
        this method can be overwritten by mixins
        """
        pass

    def configure(self):
        """
        configure is called after the agent informed the AMS that its booted. this step can be used to load
        additional information into the agent
        """
        pass

    def setup(self):
        """
        executed directly after the instance is called. user defined. is not executed in simulation.
        idea: setup communication to machine
        """
        pass

    def grpc_setup(self):
        """
        add user-defined servicers to the grpc server
        """
        pass

    def start(self):
        """
        executed directly before the loop runs - also in simulation.
        execute functions that require the connection to other agents here.
        """
        pass

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
        pass

    def simulation_start(self):
        """
        the simulation runtime schedules this event at 0.0 when started
        """
        pass

    def simulation_finish(self):
        """
        the simulation runtime schedules this event for the end of the simulation
        """
        pass

    def callback_agent_upgrade(self):
        """
        This function can be called from the agents and services to suggest 
        hat the agent should upgrate it's software (i.e. docker image)
        """
        pass

    def callback_agent_update(self):
        """
        This function can be called from the agents and services to suggest 
        that the agent should update its configuration or state
        """
        pass

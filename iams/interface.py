#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import signal

from concurrent import futures
from contextlib import contextmanager
from threading import Event
from threading import Lock
from time import sleep

import grpc
import yaml

from .agent import Servicer
from .exceptions import Continue
from .exceptions import EventNotFound
from .scheduler import Scheduler
from .utils.grpc import Grpc
from .utils.grpc import framework_channel
from .utils.grpc import get_channel_credentials
from .utils.grpc import get_server_credentials
from .utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class Agent(object):
    __hash__ = None

    # max workers = 5 * N(CPU) by default, which seems reasonable
    MAX_WORKERS = 20

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
            except FileNotFoundError:
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
        return self.__class__.__qualname__ + f"()"

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
        except grpc.RpcError as e:
            logger.debug("gRPC request failed in configure - resetting: %s - %s", e.code(), e.details())
            exit()

        if self._iams.simulation:
            # simulation loop
            while True:
                # wait for event loop
                logger.debug("waiting for wakeup event")
                self._loop_event.wait()
                self._loop_event.clear()

                # if agent should be stopped discontinue execution
                if self._stop_event.is_set():
                    break

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
            self._loop()

        logger.debug("Stopping gRPC service on %s", self._iams.agent)
        self._grpc.stop()

        if not self._iams.simulation:
            self.teardown()
            self._teardown()

        logger.debug("Stopping executor on %s", self._iams.agent)
        self._executor.shutdown(wait=False)
        logger.info("Exit %s", self._iams.agent)

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

    def _teardown(self):
        """
        this method can be overwritten by mixins
        """
        pass

    def _loop(self):
        """
        this method can be overwritten by mixins
        """
        raise NotImplementedError("A _loop method needs to be implemented")

    def _configure(self):
        """
        """
        pass

    def configure(self):
        """
        """
        pass

    def setup(self):
        """
        This gets executed on startup
        """
        pass

    def grpc_setup(self):
        """
        This gets executed on startup
        """
        pass

    def stop(self):
        """
        This gets executed on startup
        """
        self._stop_event.set()
        self._loop_event.set()

    def teardown(self):
        """
        This gets executed on teardown
        """
        pass

    def simulation_start(self):
        """
        """
        pass

    def simulation_finish(self):
        """
        """
        pass

#   def sleep(self, delay=None):
#       if self._iams.simulation is None:
#           if delay is not None and delay > 0.0:
#               self._stop_event.wait(delay)
#       return self._iams.simulation is None


class Plugin(object):
    __hash__ = None

    label = None

    def __init__(self, namespace, simulation):
        pass

    def __repr__(self):
        return self.__class__.__qualname__ + f"()"

    def __call__(self, name, image, version, config):
        kwargs = self.get_kwargs(name, image, version, config)

        return (
            self.get_labels(**kwargs),
            self.get_env(**kwargs),
            set(self.get_networks(**kwargs)),
            self.get_configured_secrets(**kwargs),
            self.get_generated_secrets(**kwargs),
        )

    def remove(self, name, config):
        pass

    def get_kwargs(self, name, image, version, config):
        return {}

    def get_labels(self, **kwargs):
        return {}

    def get_env(self, **kwargs):
        return {}

    def get_networks(self, **kwargs):
        return []

    def get_configured_secrets(self, **kwargs):
        return {}

    def get_generated_secrets(self, **kwargs):
        return []

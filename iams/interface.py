#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os
import signal

from concurrent import futures
# from threading import Event
# from threading import Lock
# from time import sleep

import grpc

from .agent import Servicer
from .utils.grpc import Grpc
from .utils.grpc import get_credentials
# from .exceptions import Continue
# from .exceptions import EventNotFound


logger = logging.getLogger(__name__)


class Agent(object):
    __hash__ = None

    # max workers = 5 * N(CPU) by default, which seems reasonable
    MAX_WORKERS = 20

    def __init__(self) -> None:
        self._credentials = get_credentials()
        self._executor = futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        # agent servicer for iams
        self._iams = Servicer(self, self._executor)
        # grpc communication (via threadpoolexecutor)
        self._grpc = Grpc(self, self._iams, self._executor)

        # self._lock = Lock()
        # self._loop_event = Event()
        # self._stop_event = Event()

        # create signals to catch sigterm events
        signal.signal(signal.SIGINT, self.__stop)
        signal.signal(signal.SIGTERM, self.__stop)

    def __repr__(self):
        return self.__class__.__qualname__ + f"()"

    def __call__(self):
        # run setup methods for controlling machines
        if self._iams.simulation is None:
            self._pre_setup()
            self.setup()
            self._post_setup()

        # load and start gRPC service
        self.grpc_setup()  # local module specification
        self._grpc_setup()  # definition on mixins
        self._grpc.start()

        # run agent configuration
        try:
            self.configure()  # local module specification
            self._configure()  # definitions on mixins
        except grpc.RpcError as e:
            logger.debug("gRPC request failed in configure - resetting: %s - %s", e.code(), e.details())
            exit()

        if self._iams.simulation is not None:
            try:
                self.simulation_init()
            except NotImplementedError:
                logger.debug("simulation_init not implemented at %s", self.__class__.__qualname__)

        # logger.debug("Informing the runtime that %s is booted", self._iams.container)
        # # signal the framework that the agent booted
        # self._iams.framework_booted()

#       # simulation
#       if self._iams.simulation is not None:
#           while True:
#               # wait for event loop
#               logger.debug("waiting for wakeup event")
#               self._loop_event.wait()
#               self._loop_event.clear()

#               # if agent should be stopped discontinue execution
#               if self._stop_event.is_set():
#                   break

#               try:
#                   callback, kwargs = next(self._iams.simulation)
#               except EventNotFound:
#                   logger.debug("Skipping - scheduled event was not found")
#                   self._iams.simulation.resume()
#                   continue

#               # execute callbacks (event based simulation)
#               logger.debug("calling %s.%s with %s", self.__class__.__qualname__, callback, kwargs)
#               try:
#                   getattr(self, callback)(**kwargs)
#               except Continue:
#                   pass
#               logger.debug("calling resume")
#               self._iams.simulation.resume()

#       # control
#       else:
#           logger.debug("Calling control loop")
#           self._loop()

        logger.debug("Stopping gRPC service on %s", os.environ.get('AMS_AGENT', 'undefined'))
        self._grpc.stop()

        if self._iams.simulation is None:
            self.teardown()
            self._teardown()

        logger.debug("Stopping executor on %s", os.environ.get('AMS_AGENT', 'undefined'))
        self._executor.shutdown(wait=False)
        logger.info("Exit %s", os.environ.get('AMS_AGENT', 'undefined'))

#   def sleep(self, delay=None):
#       if self._iams.simulation is None:
#           if delay is not None and delay > 0.0:
#               self._stop_event.wait(delay)
#       return self._iams.simulation is None

    def __stop(self, signum, frame):
        logger.info("Exit requested with code %s", signum)
        self.stop()

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

#   def _loop(self):
#       """
#       this method can be overwritten by mixins
#       """
#       raise NotImplementedError("A _loop method needs to be implemented")

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
        pass
#       self._stop_event.set()
#       self._loop_event.set()

    def teardown(self):
        """
        This gets executed on teardown
        """
        pass

    def simulation_init(self):
        """
        This gets executed on teardown
        """
        raise NotImplementedError


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

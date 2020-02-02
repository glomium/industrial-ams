#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
# import os
# import signal

# from concurrent import futures
# from threading import Event
# from threading import Lock
# from time import sleep

# import grpc

# from .agent import AgentServicer
# from .exceptions import Continue
# from .exceptions import EventNotFound
# from .utils import Grpc


logger = logging.getLogger(__name__)


class Agent(object):
    __hash__ = None


#   ETCD_TIMEOUT = 20
#   GRPC_PORT = '[::]:%s' % os.environ.get('CCM_GRPC_PORT', 80)

#   # max workers = 5 * N(CPU) by default, which seems reasonable
#   MAX_WORKERS = 20

#   def __init__(self) -> None:
#       self._executor = futures.ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
#       self._lock = Lock()
#       self._loop_event = Event()
#       self._stop_event = Event()
#       self._framework_agent = AgentServicer(self, self.ETCD_TIMEOUT, self._executor)

#       # grpc communication (via threadpoolexecutor)
#       self._grpc = Grpc(self, self._framework_agent, self._executor, self.GRPC_PORT)

#       # create signals to catch sigterm events
#       signal.signal(signal.SIGINT, self.__stop)
#       signal.signal(signal.SIGTERM, self.__stop)

#   def __repr__(self):
#       return self.__class__.__qualname__ + f"()"

#   def get_config(self):
#       return self._framework_agent.config

#   def set_config(self, data):
#       return self._framework_agent.write_config(data)

#   def get_service(self):
#       return self._framework_agent.service

#   def set_service(self, data):
#       return self._framework_agent.write_service(data)

#   def get_topology(self):
#       return self._framework_agent.topology

#   def set_topology(self, data):
#       return self._framework_agent.write_topology(data)

#   def __call__(self):

#       # we trust the data received and don't validate it
#       self._framework_agent.load_config()
#       self._framework_agent.load_service()
#       self._framework_agent.load_topology()

#       # run setup methods for controlling machines
#       if self._framework_agent.simulation is None:
#           self._pre_setup()
#           self.setup()
#           self._post_setup()

#       # load and start gRPC service
#       self.grpc_setup()  # local
#       self._grpc_setup()  # libs
#       self._grpc.start()

#       # wait until all related agents are online
#       if self._framework_agent.simulation is not None:
#           for agent in self.get_topology().keys():
#               while True:
#                   if self._framework_agent.agent_ping(agent):
#                       break
#                   logger.debug("wait for agent %s to bootup", agent)
#                   sleep(1)

#       # run agent configuration
#       try:
#           self.configure()  # local
#           self._configure()  # libs
#       except grpc.RpcError as e:
#           logger.debug("gRPC request failed in configure - resetting: %s - %s", e.code(), e.details())
#           exit()

#       if self._framework_agent.simulation is not None:
#           try:
#               self.simulation_init()
#           except NotImplementedError:
#               logger.debug("simulation_init not implemented at %s", self.__class__.__qualname__)

#       logger.debug("Informing the runtime that %s is booted", self._framework_agent.container)
#       # signal the framework that the agent booted
#       self._framework_agent.framework_booted()

#       # simulation
#       if self._framework_agent.simulation is not None:
#           while True:
#               # wait for event loop
#               logger.debug("waiting for wakeup event")
#               self._loop_event.wait()
#               self._loop_event.clear()

#               # if agent should be stopped discontinue execution
#               if self._stop_event.is_set():
#                   break

#               try:
#                   callback, kwargs = next(self._framework_agent.simulation)
#               except EventNotFound:
#                   logger.debug("Skipping - scheduled event was not found")
#                   self._framework_agent.simulation.resume()
#                   continue

#               # execute callbacks (event based simulation)
#               logger.debug("calling %s.%s with %s", self.__class__.__qualname__, callback, kwargs)
#               try:
#                   getattr(self, callback)(**kwargs)
#               except Continue:
#                   pass
#               logger.debug("calling resume")
#               self._framework_agent.simulation.resume()

#       # control
#       else:
#           logger.debug("Calling control loop")
#           self._loop()

#       logger.debug("Stopping gRPC service on %s", os.environ.get('AMS_AGENT', 'undefined'))
#       self._grpc.stop()

#       if self._framework_agent.simulation is None:
#           self.teardown()
#           self._teardown()

#       logger.debug("Stopping executor on %s", os.environ.get('AMS_AGENT', 'undefined'))
#       self._executor.shutdown(wait=False)
#       logger.info("Exit %s", os.environ.get('AMS_AGENT', 'undefined'))

#   def sleep(self, delay=None):
#       if self._framework_agent.simulation is None:
#           if delay is not None and delay > 0.0:
#               self._stop_event.wait(delay)
#       return self._framework_agent.simulation is None

#   def __stop(self, signum, frame):
#       logger.info("Exit requested with code %s", signum)
#       self.stop()

#   def _grpc_setup(self):
#       """
#       this method can be overwritten by mixins
#       """
#       pass

#   def _pre_setup(self):
#       """
#       this method can be overwritten by mixins
#       """
#       pass

#   def _post_setup(self):
#       """
#       this method can be overwritten by mixins
#       """
#       pass

#   def _teardown(self):
#       """
#       this method can be overwritten by mixins
#       """
#       pass

#   def _loop(self):
#       """
#       this method can be overwritten by mixins
#       """
#       raise NotImplementedError("A _loop method needs to be implemented")

#   def _configure(self):
#       """
#       """
#       pass

#   def configure(self):
#       """
#       """
#       pass

#   def setup(self):
#       """
#       This gets executed on startup
#       """
#       pass

#   def grpc_setup(self):
#       """
#       This gets executed on startup
#       """
#       pass

#   def stop(self):
#       """
#       This gets executed on startup
#       """
#       self._stop_event.set()
#       self._loop_event.set()

#   def teardown(self):
#       """
#       This gets executed on teardown
#       """
#       pass

#   def simulation_init(self):
#       """
#       This gets executed on teardown
#       """
#       raise NotImplementedError

#   def get_process_kwargs(self):
#       return self.PROCESS_KWARGS or {}


class Plugin(object):
    __hash__ = None

    label = None

    def get_kwargs(self, config):
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

    def __call__(self, config):
        kwargs = self.get_kwargs(config)

        return (
            self.get_labels(**kwargs),
            self.get_env(**kwargs),
            set(self.get_networks(**kwargs)),
            self.get_configured_secrets(**kwargs),
            self.get_generated_secrets(**kwargs),
        )

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import os

from uuid import uuid1

import grpc

from google.protobuf.empty_pb2 import Empty

from .proto import agent_pb2_grpc
from .proto import framework_pb2_grpc
from .proto import framework_pb2
from .proto import simulation_pb2_grpc
from .proto.agent_pb2 import ConnectionResponse
from .proto.agent_pb2 import PingResponse
from .proto.agent_pb2 import ServiceResponse
from .proto.framework_pb2 import WakeAgent
from .proto.simulation_pb2 import EventRegister
from .stub import AgentStub
from .utils import agent_required
from .utils import framework_channel
from .utils import grpc_retry


logger = logging.getLogger(__name__)


AgentData = framework_pb2.AgentData


class AgentServicer(agent_pb2_grpc.AgentServicer):

    def __init__(self, main, timeout, threadpool, timeout_buffer=5):
        self.address = os.environ.get('AMS_ADDRESS', None)
        self.container = os.environ.get('AMS_AGENT', None)
        self.etcd_server = os.environ.get('AMS_ETCD_SERVER', None)
        self.framework = os.environ.get('AMS_CORE', None)
        self.type = os.environ.get('AMS_TYPE', None)

        assert self.container is not None, 'Must define AMS_AGENT in environment'
        assert self.etcd_server is not None, 'Must define AMS_ETCD_SERVER in environment'
        assert self.framework is not None, 'Must define AMS_CORE in environment'
        assert self.type is not None, 'Must define AMS_TYPE in environment'

        self.main = main
        self.threadpool = threadpool

        if self.type == "simulation":
            self.simulation = SimulationRuntime(self, main)
        else:
            self.simulation = None

        self.etcd_prefix = f"agents/{self.container}/".encode('utf-8')
        self.etcd_client = Etcd3Client(host=self.etcd_server, timeout=timeout)
        self.etcd_lease = self.etcd_client.lease(timeout + timeout_buffer)

        # variables used by agent
        self.config = {}
        self.heartbeat(timeout, init=True)
        self.state = None
        self.service = {}
        self.topology = {}

    def set_state(self, state):
        # key = f'agents/{self.container!s}/state'  # TODO
        key = f'agents/{self.container!s}/status'

        if self.state != state:
            self.etcd_client.put(key, state, lease=self.etcd_lease)
            self.state = state

    def set_idle(self):
        self.set_state(States.IDLE)

    def set_busy(self):
        self.set_state(States.BUSY)

    def set_waiting(self):
        self.set_state(States.WAITING)

    def set_error(self):
        self.set_state(States.ERROR)

    def set_maintenance(self):
        self.set_state(States.MAINTENANCE)

    def load_config(self):
        key = f'agents/{self.container!s}/config'
        self.config = self.load(key)

    def load_service(self):
        key = f'agents/{self.container!s}/service'
        self.service = self.load(key)

    def load_topology(self):
        key = f'agents/{self.container!s}/topology'
        self.topology = self.load(key)

    def load(self, key):
        data, metadata = self.etcd_client.get(key)
        try:
            data = json.loads(data)
        except TypeError:
            data = {}
        except json.JSONDecodeError as e:
            logger.exception(e)
            data = {}
        logger.debug("loaded %s from %s", data, key)
        return data

    def write_config(self, data):
        key = f'agents/{self.container!s}/config'
        if self.write(key, data):
            self.config = data
            return True
        return False

    def write_service(self, data):
        key = f'agents/{self.container!s}/service'
        if self.write(key, data):
            self.service = data
            return True
        return False

    def write_topology(self, data):
        key = f'agents/{self.container!s}/topology'
        if self.write(key, data):
            self.topology = data
            return True
        return False

    def write(self, key, data):
        data = json.dumps(data)
        self.etcd_client.put(key, data)
        logger.debug("written %s to %s", data, key)
        return True

    def stop(self):
        self.etcd_lease.revoke()

    def heartbeat(self, timeout, init=False):
        if not init:
            if hasattr(self.main, "heartbeat"):
                logger.debug("heartbeat called")
                self.main.heartbeat()
            self.etcd_lease.refresh()
            self.main._stop_event.wait(timeout)

        if not self.main._stop_event.is_set():
            self.threadpool.submit(self.heartbeat, timeout)

    def get_kwargs(self, request, context):
        if not request.agent:
            message = 'No agent given in request.'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if request.kwargs:
            kwargs = msgpack.loads(request.kwargs)
        else:
            kwargs = {}

        kwargs.update({
            "name": request.name,
            "image": request.image,
            "version": request.version,
        })
        return kwargs

    def call_main(self, name, context, kwargs):
        try:
            callback = getattr(self.main, 'framework_%s' % name)
        except AttributeError:
            message = 'Method framework_%s not available!' % name
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, message)

        if not callback(**kwargs):
            message = 'No Permissions to call framework_%s.' % name
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

    # grpc call
    @agent_required
    def connection_get(self, request, context):
        for agent, data in self.topology.items():
            for item in data:
                image = item.get("image", None)
                version = item.get("version", None)
                interface = item.get("interface", None)
                kwargs = item.get("kwargs", {})
                yield ConnectionResponse(
                    agent=agent,
                    image=image,
                    version=version,
                    interface=interface,
                    kwargs=msgpack.dumps(kwargs),
                )

    # grpc call
    @agent_required
    def service_get(self, request, context):
        logger.debug("service_get called: %s", self.service)
        for service, kwargs in self.service.items():
            yield ServiceResponse(
                agent=self.container,
                image=os.environ.get('AMS_IMAGE', None),
                version=os.environ.get('AMS_VERSION', None),
                service=service,
                kwargs=msgpack.dumps(kwargs or {}),
            )

    # grpc call
    @agent_required
    def connection_add(self, request, context):
        kwargs = self.get_kwargs(request, context)
        if self.call_main("connection_add", context, kwargs):
            if request.kwargs:
                self.connections[kwargs["interface"]][kwargs["agent"]] = {
                    "image": kwargs["image"],
                    "version": kwargs["version"],
                    "kwargs": msgpack.loads(request.kwargs, raw=False),
                }
                self.connections[kwargs["agent"]] = {
                    "image": kwargs["image"],
                    "version": kwargs["version"],
                    "kwargs": None,
                }

            # TODO use etcd to store connection information
            return Empty()

    # grpc call
    @agent_required
    def connection_del(self, request, context):
        kwargs = self.get_kwargs(request, context)
        if self.call_main("connection_del", context, kwargs):
            try:
                del self.connections[kwargs["interface"]][kwargs["agent"]]
            except KeyError:
                message = 'There is no agent %s at interface %s' % (kwargs["agent"], kwargs["interface"])
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

            # TODO use etcd to store connection information
            return Empty()

    # grpc call
    def simulation_continue(self, request, context):
        if self.simulation is None:
            message = 'This function is only availabe when agenttype is set to simulation'
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        logger.debug("simulation_continue called")
        self.simulation.event_trigger(request.uuid, request.time)
        return Empty()

    # grpc call
    @agent_required
    def ping(self, request, context):
        return PingResponse(
            image=os.environ.get('AMS_IMAGE', None),
            version=os.environ.get('AMS_VERSION', None),
        )

    def agent_ping(self, agent):
        try:
            with framework_channel(agent) as channel:
                stub = AgentStub(channel)
                response = stub.ping(Empty(), timeout=10)
            logger.debug("Ping response (%s) %s:%s", agent, response.image, response.version)
            return True
        except grpc.RpcError as e:
            logger.debug("Ping response %s: %s from %s", e.code(), e.details(), agent)
            return False

    def agent_connection_get(self, agent):
        with framework_channel(agent) as channel:
            stub = AgentStub(channel)
            logger.debug("calling connection_get on %s", agent)
            for response in stub.connection_get(Empty(), timeout=10):
                data = {
                    "agent": response.agent,
                    "image": response.image,
                    "version": response.version,
                    "interface": response.interface,
                    "kwargs": msgpack.loads(response.kwargs, raw=False),
                }
                logger.debug("connection list of agent %s: %s", agent, data)
                yield data

    def agent_service_get(self, agent):
        with framework_channel(agent) as channel:
            stub = AgentStub(channel)
            logger.debug("calling service_get on %s", agent)
            for response in stub.service_get(Empty(), timeout=10):
                data = {
                    "agent": response.agent,
                    "image": response.image,
                    "version": response.version,
                    "service": response.service,
                    "kwargs": msgpack.loads(response.kwargs, raw=False),
                }
                logger.debug("service list of agent %s: %s", agent, data)
                yield data

    # def simulation_resume(self, delay=None) -> bool:
    #     if self.simulation is None:
    #         return False
    #     logger.error("Deprecation!!")
    #     if delay is None:
    #         request = EventRegister()
    #     else:
    #         request = EventRegister(uuid=uuid1().bytes, delay=delay)
    #     try:
    #         with framework_channel() as channel:
    #             stub = SimulationStub(channel)
    #             stub.resume(request, timeout=10)
    #         if delay is not None:
    #             logger.debug("continue with execution in %s seconds", delay)
    #         return True
    #     except grpc.RpcError as e:
    #         logger.exception("error %s in simulation_resume: %s", e.code(), e.details())
    #         return False

    def framework_booted(self) -> bool:
        with framework_channel() as channel:
            stub = FrameworkStub(channel)
            stub.booted(Empty(), timeout=10)
        return True

    def framework_destroy(self) -> bool:
        logger.debug("calling AMS to be killed")
        with framework_channel() as channel:
            stub = FrameworkStub(channel)
            stub.destroy(Empty(), timeout=10)
        return True

    def framework_sleep(self) -> bool:
        logger.debug("calling AMS to be sent to sleep")
        with framework_channel() as channel:
            stub = FrameworkStub(channel)
            stub.sleep(Empty(), timeout=10)
        return True

    def framework_upgrade(self) -> bool:
        with framework_channel() as channel:
            stub = FrameworkStub(channel)
            stub.upgrade(Empty(), timeout=10)
        return True

    def framework_wake(self, other) -> bool:
        with framework_channel() as channel:
            stub = FrameworkStub(channel)
            stub.upgrade(WakeAgent(agent=other), timeout=10)
        return True


AgentServicer.__doc__ = agent_pb2_grpc.AgentServicer.__doc__

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import queue
import random
import re

from heapq import heappush
from heapq import heappop
from threading import Event
from uuid import UUID

import grpc

from docker import errors as docker_errors
from google.protobuf.empty_pb2 import Empty

from .proto import agent_pb2
from .proto import simulation_pb2
from .proto import simulation_pb2_grpc
from .proto import framework_pb2
from .proto import framework_pb2_grpc
from .stub import AgentStub
from .utils.auth import permissions
from .utils.docker import Docker
from .utils.grpc import framework_channel
from .utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


def generate_seed():
    return bytearray(random.getrandbits(8) for x in range(12)).hex()


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, client, cfssl, servername, namespace, args, credentials, threadpool, plugins):
        self.args = args
        self.cfssl = cfssl
        self.credentials = credentials
        self.threadpool = threadpool
        self.servername = servername
        self.namespace = namespace
        self.booting = set()
        self.event = Event()
        self.event.set()

        self.docker = Docker(client, cfssl, servername, namespace, args.namespace, args.simulation, plugins)

        self.RE_NAME = re.compile(r'^(%s_)?([a-zA-Z][a-zA-Z0-9-]+[a-zA-Z0-9])$' % self.args.namespace[0:4])

    def set_booting(self, name):
        logger.debug("adding %s to %s", name, self.booting)
        self.booting.add(name)
        self.event.clear()

    def del_booting(self, name):
        logger.debug("removing %s from %s", name, self.booting)
        try:
            self.booting.remove(name)
            if not self.booting:
                self.event.set()
        except KeyError:
            pass

    # RPCs
    @permissions(is_optional=True)
    def renew(self, request, context):

        if context._agent is not None:
            request.name = context._agent
        else:
            # connect to ping-rpc on name and check if connection breaks due to an invalid certificate

            if validate_certificate(request.name):
                message = "Client-validation failed"
                context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
            else:
                request.hard = True

        if not request.name:
            message = "Agent name not set"
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        # Use a seperate thread to renew the certificate in docker's secrets
        if request.hard:
            self.threadpool.submit(self.docker.set_service, name=request.name, update=True)
            return framework_pb2.RenewResponse()

        # mark container as booting
        self.set_booting(request.name)

        # generate pk and certificate and send it
        # the request is authenticated and origins from an agent, i.e it contains image and version
        response = self.cfssl.get_certificate(request.name, image=context._image, version=context._version)
        return framework_pb2.RenewResponse(
            private_key=response["result"]["private_key"],
            certificate=response["result"]["certificate"],
        )

    # RPCs

    @permissions(has_agent=True)
    def booted(self, request, context):
        logger.debug('booted called from %s', context._agent)
        self.del_booting(context._agent)
        return Empty()

    def images(self, request, context):
        """
        """
        for image in self.client.images.list(filters={'label': ["ams.services.agent=true"]}):
            for tag in image.tags:
                pass
            # TODO yield data

    @permissions(has_agent=True, has_groups=["root", "web"])
    def agents(self, request, context):
        """
        """
        filters = list(request.filter) + [f"iams.namespace={self.args.namespace}"]
        for service in self.docker.client.services.list(filters={'label': filters}):
            image, version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)  # noqa
            yield framework_pb2.AgentResponse(
                name=service.name,
                image=image,
                version=version,
            )

    @permissions(has_agent=True, has_groups=["root", "web"])
    def update(self, request, context):

        logger.debug('update called from %s', context._agent)
        if context._agent:
            request.name = context._agent

        try:
            created = self.docker.set_service(
                request.name,
                image=request.image,
                version=request.version,
                address=request.address,
                port=request.port,
                config=request.config,
                autostart=request.autostart,
            )

        except docker_errors.ImageNotFound:
            message = f'Could not find {request.image}:{request.version}'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        except docker_errors.NotFound:
            message = f'Could not find {request.name}'
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        if created:
            self.set_booting(request.name)

        return framework_pb2.AgentData()

    @permissions(has_agent=True, has_groups=["root", "web"])
    def create(self, request, context):
        logger.debug('create called from %s', context._username)

        regex = self.RE_NAME.match(request.name)
        if regex:
            name = self.args.namespace[0:4] + '_' + regex.group(2)
        else:
            message = 'A name with starting with a letter, ending with an alphanumerical chars and' \
                      'only containing alphanumerical values and hyphens is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.image:
            message = 'An image is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.version:
            message = 'A version is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        try:
            self.docker.set_service(
                name,
                image=request.image,
                version=request.version,
                address=request.address,
                port=request.port,
                config=request.config,
                autostart=request.autostart,
                create=True,
                seed=getattr(context, '_seed', None),
            )

        except docker_errors.ImageNotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, e)

        self.set_booting(name)
        return framework_pb2.AgentData()

    @permissions(has_agent=True, has_groups=["root", "web"])
    def destroy(self, request, context):
        logger.debug('destroy called from %s', context._agent)
        try:
            self.docker.del_service(context._agent)
        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)
        return Empty()

    @permissions(has_agent=True)
    def sleep(self, request, context):
        logger.debug('sleep called from %s', context._agent)
        try:
            self.docker.set_scale(context._agent, 0)
        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)
        return Empty()

    @permissions(has_agent=True)
    def upgrade(self, request, context):
        logger.debug('upgrade called from %s', context._agent)
        self.docker.set_service(
            context._agent,
            update=True,
        )
        return Empty()

#   @auth_required
#   def wake(self, request, context):
#       logger.debug('wake called from %s', context._agent)
#       service = self.get_service(context, context._agent)
#       if service.attrs['Spec']['Mode']['Replicated']['Replicas'] > 0:
#           logger.debug('scale service %s to 1', context._agent)
#           service.scale(1)
#       return Empty()


class SimulationServicer(simulation_pb2_grpc.SimulationServicer):

    def __init__(self, agent_servicer):
        self.event = Event()
        self.servicer = agent_servicer

        self.heap = []
        self.queue = None
        self.simulation = False
        self.time = 0.0

    def reset(self, callback=True):
        if callback:
            logger.info("Resetting simulation runtime")
        else:
            logger.error("Simulatddion canceled - resetting")

        self.heap = []
        self.queue = None
        self.simulation = False

        # kill all agents
        for service in self.servicer.docker.get_service():
            self.servicer.docker.del_service(service)

    @permissions(is_optional=True)
    def start(self, request, context):
        if self.simulation:
            message = 'A simulation is currently running'
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, message)
        self.simulation = True
        self.time = 0.0

        self.heap = []
        self.queue = queue.Queue()
        self.time = 0.0
        agent = None

        # generate a seed for pseudo-random function (make simulations repeatable)
        if request.seed:
            seed = request.seed
        else:
            seed = generate_seed()
        random.seed(seed)
        logger.info("setting seed for random values to %s", seed)

        # create agents
        logger.info("Creating agents from config")
        for agent in request.agents:
            try:
                context._seed = generate_seed()
                self.servicer.create(agent.container, context)
            except Exception:
                self.reset(False)
                raise

        logger.info("Starting simulation")
        context.add_callback(self.reset)
        agent = None

        while True:

            # waiting for containers to boot
            if not self.servicer.event.is_set():
                logger.debug("Waiting for containers to boot")
                self.servicer.event.wait()

            # stop simulation if agent does not reply for 60 seconds
            if agent is not None and not self.event.wait(30):
                logger.info("waited 30s on the respone of agent %s", agent)
            if agent is not None and not self.event.wait(30):
                logger.warning("waited 60s on the respone of agent %s - closing simulation", agent)
                break

            try:
                self.time, delay, agent, uuid = heappop(self.heap)
            except IndexError:
                logger.info("Simulation finished - no more events in queue")
                break

            # send information from last step to client
            logger.debug("Dumping data to client")
            try:
                while True:
                    kwargs = self.queue.get_nowait()
                    yield simulation_pb2.SimulationData(**kwargs)  # TODO?
                    self.queue.task_done()
            except queue.Empty:
                logger.debug("Dumped all data to client")
                pass

            # Stop simulation if time is reached
            if request.until is not None and self.time > request.until:
                logger.info("Simulation finished - time limit reached")
                break

            with framework_channel(hostname=agent, credentials=self.servicer.credentials) as channel:
                logger.info(
                    "continue execution of simulation on %s at %s (%s)",
                    agent,
                    self.time,
                    UUID(bytes=uuid),
                )
                stub = AgentStub(channel)
                stub.resume_simulation(agent_pb2.SimulationData(uuid=uuid, time=self.time), timeout=10)

            # clear event to wait for the finish of the next simulation step
            self.event.clear()

            logger.debug("Execute next simulation step")

    @permissions(has_agent=True)
    def schedule(self, request, context):
        time = self.time + request.delay
        logger.debug("Adding event at %s for agent %s (delay=%s)", time, context._agent, request.delay)
        # If we have two events at the same time, we use the negative delay
        # to decide which event was added first. this reduces the
        # possibility to run into infinite loops if one agents decides to wait
        # for an event on another agent
        heappush(self.heap, (time, -request.delay, context._agent, request.uuid))
        return simulation_pb2.EventScheduleResponse(time=time)

    @permissions(has_agent=True)
    def resume(self, request, context):
        logger.debug("Simulation resumed from agent %s", context._agent)
        self.event.set()
        return Empty()

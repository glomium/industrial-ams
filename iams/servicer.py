#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os
import random
import re
import time

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
from .utils.arangodb import Arango
from .utils.auth import permissions
from .utils.docker import Docker
from .utils.grpc import framework_channel
from .utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


def generate_seed():
    return bytearray(random.getrandbits(8) for x in range(12)).hex()


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, runtime, client, cfssl, cloud, args, credentials, threadpool, plugins, runtests):
        self.runtime = runtime
        self.args = args
        self.cfssl = cfssl
        self.cloud = cloud
        self.credentials = credentials
        self.runtests = runtests
        self.threadpool = threadpool

        self.booting = set()
        self.event = Event()
        self.event.set()

        self.docker = Docker(client, cfssl, cloud, args.namespace, args.simulation, plugins)
        self.arango = Arango(
            cloud.namespace,
            hosts=os.environ.get("IAMS_ARANGO_HOSTS", "http://tasks.arangodb:8529"),
            docker=self.docker,
        )

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

    # RPC
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
            self.threadpool.submit(self.runtime.update_agent, framework_pb2.AgentData(name=request.name), update=True)  # noqa
            # self.threadpool.submit(self.docker.set_service, name=request.name, update=True)
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

    # RPC
    @permissions(has_agent=True)
    def booted(self, request, context):
        logger.debug('booted called from %s', context._agent)
        self.del_booting(context._agent)
        return Empty()

    # RPC
    # @permissions(has_agent=True, has_groups=["root", "web"])
    # def agents(self, request, context):
    #     """
    #     """
    #     filters = list(request.filter) + [f"iams.namespace={self.args.namespace}"]
    #     for service in self.docker.client.services.list(filters={'label': filters}):
    #         image, version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)  # noqa
    #         yield framework_pb2.AgentData(
    #             name=service.name,
    #             image=image,
    #             version=version,
    #         )

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def update(self, request, context):
        logger.debug('Update called from %s', context._username)
        request.name = self.get_agent_name(context, request.name)

        try:
            created = self.runtime.update_agent(request)
            # created = self.docker.set_service(
            #     name,
            #     image=request.image,
            #     version=request.version,
            #     address=request.address,
            #     port=request.port,
            #     config=request.config,
            #     autostart=request.autostart,
            #     placement_constraints=request.constraints,
            #     placement_preferences=request.preferences,
            # )
            logger.debug("update_agent responded with created=%s", created)

        except docker_errors.ImageNotFound:
            message = f'Could not find image {request.image}:{request.version}'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        except docker_errors.NotFound as e:
            message = str(e)
            logger.debug(message)
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        if created:
            self.set_booting(request.name)

        return framework_pb2.AgentData(name=request.name)

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def create(self, request, context):
        logger.debug('create called from %s', context._username)

        regex = self.RE_NAME.match(request.name)
        if regex:
            request.name = self.args.namespace[0:4] + '_' + regex.group(2)
        else:
            message = 'A name with starting with a letter, ending with an alphanumerical chars and ' \
                      'only containing alphanumerical values and hyphens is required to define agents'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.image:
            message = 'An image is required to define agents'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.version:
            message = 'A version is required to define agents'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        try:
            self.runtime.update_agent(request)
            # self.docker.set_service(
            #     name,
            #     image=request.image,
            #     version=request.version,
            #     address=request.address,
            #     port=request.port,
            #     config=request.config,
            #     autostart=request.autostart,
            #     create=True,
            #     seed=getattr(context, '_seed', None),
            #     placement_constraints=request.constraints,
            #     placement_preferences=request.preferences,
            # )

        except docker_errors.ImageNotFound:
            message = f'Could not find image {request.image}:{request.version}'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        except docker_errors.NotFound as e:
            message = f'{e!s}'
            logger.debug(message)
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        except ValueError as e:
            message = f'{e!s}'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        self.set_booting(request.name)
        self.create_callback(request.name)
        return framework_pb2.AgentData(name=request.name)

    def create_callback(self, name):
        """
        the create_callback is overwritten by the simulation runtime.
        it creates two events (start and stop of service), after a service is created
        """
        pass

    def get_agent_name(self, context, name):
        if context._agent is None and name is None:
            message = 'Need to give agent name in request'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if context._agent:
            return context._agent

        try:
            regex = self.RE_NAME.match(name)
            return self.args.namespace[0:4] + '_' + regex.group(2)
        except AttributeError:
            message = 'Given an invalid agent name (%s) in request' % name
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def destroy(self, request, context):
        logger.debug('Destroy called from %s', context._username)
        agent = self.get_agent_name(context, request.name)

        try:
            self.docker.del_service(agent)
        except docker_errors.NotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{e!s}')

        # TODO: remove agent from arango db
        return Empty()

    # RPC
    @permissions(has_agent=True)
    def sleep(self, request, context):
        logger.debug('sleep called from %s', context._agent)
        try:
            self.docker.set_scale(context._agent, 0)
        except docker_errors.NotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{e!s}')
        return Empty()

    # RPC
    @permissions(has_agent=True)
    def upgrade(self, request, context):
        logger.debug('upgrade called from %s', context._agent)
        self.runtime.update_agent(framework_pb2.AgentData(name=request.name), update=True)  # noqa
        # self.docker.set_service(
        #     context._agent,
        #     update=True,
        # )
        return Empty()

    # RPC
    @permissions(has_agent=True)
    def wake(self, request, context):
        logger.debug('wake called from %s', context._agent)
        service = self.get_service(context, context._agent)
        if service.attrs['Spec']['Mode']['Replicated']['Replicas'] > 0:
            logger.debug('scale service %s to 1', context._agent)
            service.scale(1)
        return Empty()

    # RPC
    @permissions(has_agent=True)
    def topology(self, request, context):
        logger.debug('topology called from %s', context._agent)

        # iterate over node.edges and change name with regex
        for edge in request.edges:
            if edge.agent is not None:
                regex = self.RE_NAME.match(edge.agent)
                if regex:
                    edge.agent = self.args.namespace[0:4] + '_' + regex.group(2)
                else:
                    message = 'A name with starting with a letter, ending with an alphanumerical chars and ' \
                              'only containing alphanumerical values and hyphens is required to define agents'
                    logger.debug(message)
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        self.arango.create_agent(context._agent, request)
        return request


class SimulationServicer(simulation_pb2_grpc.SimulationServicer):

    def __init__(self, agent_servicer, event, runtests):
        self.event = event
        self.runtests = runtests
        self.servicer = agent_servicer
        agent_servicer.create_callback = self.create_callback

        self.heap = []
        self.simulation = False
        self.time = 0.0

    def add_event(self, delay, agent, uuid):
        scheduled_time = self.time + delay
        if self.until and scheduled_time > self.until:
            return None

        logger.debug("Adding event at %s for agent %s (delay=%s)", scheduled_time, agent, delay)
        # If we have two events at the same time, we use the negative delay
        # to decide which event was added first. this reduces the
        # possibility to run into infinite loops if one agents decides to wait
        # for an event on another agent
        heappush(self.heap, (scheduled_time, -delay, agent, uuid, False))

    def create_callback(self, name):
        heappush(self.heap, (self.time, 0.0, name, None, False))
        if self.until:
            heappush(self.heap, (self.until, 0.0, name, None, True))

    def reset(self, callback=True):
        if callback:
            logger.info("Resetting simulation runtime")
        else:
            logger.error("Simulation canceled - resetting")

        self.heap = []
        self.simulation = False

        # kill all agents
        for service in self.servicer.docker.get_service():
            self.servicer.docker.del_service(service)

    @permissions(has_agent=True)
    def schedule(self, request, context):
        self.add_event(request.delay, context._agent, request.uuid)
        return Empty()

    @permissions(is_optional=True)
    def start(self, request, context):
        if self.simulation:
            message = 'A simulation is currently running'
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, message)
        self.simulation = True
        self.time = 0.0
        self.until = request.until or None

        self.heap = []
        self.time = 0.0
        agent = None

        # generate a seed for pseudo-random function (make simulations repeatable)
        if request.seed:
            seed = request.seed
        else:
            seed = generate_seed()
        random.seed(seed)
        logger.info("setting seed for random values to %s", seed)

        # reset booting information on servicer
        self.servicer.booting = set()

        # create agents
        logger.info("Creating agents from config")
        for agent in request.agents:
            try:
                context._seed = generate_seed()
                self.servicer.create(agent.container, context)
            except Exception:
                self.reset(False)
                raise

        # create callback if connection breaks
        context.add_callback(self.reset)

        logger.info("Starting simulation")
        agent = None

        yield simulation_pb2.SimulationData(log=agent_pb2.SimulationLog(text="simulation started"))
        count = 0
        dt = time.time()

        while True:

            # waiting for containers to boot
            if not self.servicer.event.is_set():
                logger.debug("Waiting for containers to boot")
                self.servicer.event.wait()

            try:
                self.time, delay, agent, uuid, finish = heappop(self.heap)
            except IndexError:
                logger.info("Simulation finished - no more events in queue")
                break

            # # Stop simulation if time is reached
            # if self.time > self.until:
            #     logger.info("Simulation finished - time limit reached")
            #     break

            if uuid:
                logger.info(
                    "continue execution of simulation on %s at %s (%s)",
                    agent,
                    self.time,
                    UUID(bytes=uuid),
                )
            elif finish:
                logger.info(
                    "stop execution of simulation on %s",
                    agent,
                )
            else:
                logger.info(
                    "start execution of simulation on %s",
                    agent,
                )

            with framework_channel(hostname=agent, credentials=self.servicer.credentials) as channel:
                stub = AgentStub(channel)
                request = agent_pb2.SimulationRequest(uuid=uuid, time=self.time, finish=finish)
                for r in stub.run_simulation(request, timeout=10):
                    if r.schedule.ByteSize():
                        self.add_event(r.schedule.delay, agent, r.schedule.uuid)

                    elif r.metric.ByteSize() or r.log.ByteSize():
                        logger.debug("got metric or log - %s %s", r.metric, r.log)
                        yield simulation_pb2.SimulationData(
                            name=self.servicer.RE_NAME.match(agent).group(2),
                            time=self.time,
                            log=r.log,
                            metric=r.metric,
                        )
            logger.info("Connection to %s closed", agent)

            count += 1
            logger.debug("Execute next simulation step")

        # if logging.root.level <= logging.ERROR or True:  # FIXME: debug
        #     logger.info("===== EDGES:")
        #     edges = [
        #         (x["_from"].split("/", 1)[1], x["_to"].split("/", 1)[1])
        #         for x in self.servicer.arango.db.graph("connections").edge_collection('logical').all()
        #     ]
        #     for f, t in sorted(edges):
        #         logger.info("== %s -> %s", f, t)

        #     for name in [x["name"] for x in self.servicer.arango.db.collections() if x["name"][0] != "_"]:
        #         collection = self.servicer.arango.db.collection(name)
        #         logger.info("%s: %s", name, list(collection.all()))

        dt = time.time() - dt
        yield simulation_pb2.SimulationData(
            time=self.time,
            log=agent_pb2.SimulationLog(text="simulation ended - simulated %s steps (%.1f/s)" % (count, count / dt)),
        )

    @permissions(is_optional=True)
    def shutdown(self, request, context):
        if self.simulation:
            message = 'A simulation is currently running'
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, message)
        self.event.set()
        return Empty()

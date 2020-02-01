#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import re
# import os

import grpc

from docker import errors as docker_errors
from google.protobuf.empty_pb2 import Empty

# from .proto import agent_pb2
from .proto import agent_pb2_grpc
from .proto import simulation_pb2
from .proto import simulation_pb2_grpc
from .proto import framework_pb2
from .proto import framework_pb2_grpc

from .utils.auth import permissions
from .utils.cfssl import get_certificate
from .utils.docker import Docker


logger = logging.getLogger(__name__)


class SimulationServicer(simulation_pb2_grpc.SimulationServicer):

    def __init__(self, parent):
        self.parent = parent

    def test(self, request, context):
        if self.parent.simulation is None:
            message = 'No simulation is currently running'
            context.abort(grpc.StatusCode.NOT_FOUND, message)

    def add_event(self, agent, uuid, delay, allow_next):
        if uuid:
            time, start_next = self.parent.simulation.add_event(agent, uuid, delay)
            logger.debug(
                "%s scheduled a new event with a delay of %s at %s",
                agent,
                delay,
                time,
            )
            return start_next and allow_next, simulation_pb2.EventSchedule(time=time)
        return allow_next, simulation_pb2.EventSchedule()

    @permissions(has_agent=True)
    def resume(self, request, context):
        self.test(request, context)
        start_next, response = self.add_event(context._agent, request.uuid, request.delay, True)
        if start_next:
            logger.debug("%s requested the next step", context._agent)
            # resume simulation runtime
            self.parent.simulation.event.set()
        return response

    @permissions(has_agent=True)
    def schedule(self, request, context):
        self.test(request, context)
        start_next, response = self.add_event(context._agent, request.uuid, request.delay, False)
        return response


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, args, credentials, threadpool, plugins={}):
        self.args = args
        self.credentials = credentials
        self.threadpool = threadpool

        if args.simulation:
            self.prefix = "sim"
        else:
            self.prefix = "prod"

        self.docker = Docker(args.namespace, self.prefix)
        self.plugins = plugins

        self.RE_NAME = re.compile(r'^(%s_)?([\w]+)$' % self.prefix[0])

    # RPCs

    @permissions(is_optional=True)
    def renew(self, request, context):

        if context._agent is not None:
            request.name = context._agent
        else:
            # connect to ping-rpc on name and check if connection breaks due to an invalid certificate
            try:
                with grpc.secure_channel('%s:%s' % (request.name, self.args.agent_port), self.credentials) as channel:
                    stub = agent_pb2_grpc.PingStub(channel)
                    stub.ping(Empty())
            except grpc.RpcError as e:
                code = e.code()
                if code in [grpc.StatusCode.UNAVAILABLE]:
                    request.hard = True
                else:
                    message = "Client-validation failed"
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
            else:
                message = "Client-validation failed"
                context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        if not request.name:
            message = "Agent name not set"
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        # Use a seperate thread to renew the certificate in docker's secrets
        if request.hard:
            self.threadpool.submit(self.docker.set_service, name=request.name, update=True)
            return framework_pb2.RenewResponse()

        # generate pk and certificate and send it
        # the request is authenticated and origins from an agent, i.e it contains image and version
        response = get_certificate(request.name, image=context._image, version=context._version)
        return framework_pb2.RenewResponse(
            private_key=response["result"]["private_key"],
            certificate=response["result"]["certificate"],
        )

#   # RPCs

#   # === TODO ===

#   def images(self, request, context):
#       """
#       """
#       for image in self.client.images.list(filters={'label': ["ams.services.agent=true"]}):
#           for tag in image.tags:
#               pass
#           # TODO yield data

#   @agent_required
#   def booted(self, request, context):
#       logger.debug('booted called from %s', context._agent)
#       try:
#           self.parent.agent_booted(context._agent)
#       except docker_errors.NotFound:
#           message = 'Could not find %s' % context._agent
#           context.abort(grpc.StatusCode.NOT_FOUND, message)
#       return Empty()

#   # === END TODO

    def agents(self, request, context):
        """
        """
        for service in self.client.services.list(filters={'label': ["iams.namespace=%s" % self.prefix]}):
            name, address, image, version, config, autostart = self.get_service_data(service)
            yield framework_pb2.AgentData(
                name=service.name,
                image=image,
                version=version,
                address=address,
                config=config,
                autostart=autostart,
            )

    @permissions(has_agent=True, has_groups=["root", "web"])
    def update(self, request, context):
        logger.debug('update called from %s', context._agent)
        try:
            self.docker.set_service(
                context._agent,
                image=request.image,
                version=request.version,
                address=request.address,
                port=request.port,
                config=request.config,
                autostart=request.autostart,
            )

        except docker_errors.ImageNotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        return framework_pb2.AgentData()

    @permissions(has_agent=True, has_groups=["root", "web"])
    def create(self, request, context):
        logger.debug('create called from %s', context._agent)

        if self.RE_NAME.match(request.name):
            name = self.prefix[0] + '_' + request.name
        else:
            message = 'A name containing no special chars is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.image:
            message = 'An image is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.version:
            message = 'A version is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if request.config:
            try:
                config = json.loads(request.config)
            except json.JSONDecodeError:
                message = 'Config is not JSON parsable'
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

            if not isinstance(config, dict):
                message = 'Config needs to be a json-dictionary %s' % request.config
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
            )

        except docker_errors.ImageNotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, e)

        return framework_pb2.AgentData()

    @permissions(has_agent=True, has_groups=["root", "web"])
    def destroy(self, request, context):
        logger.debug('destroy called from %s', context._agent)
        try:
            self.docker.del_service(context._agent)
        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        # TODO add destroy callbacks for plugins!
        # # cleanup database
        # for path in [
        #     f'agents/{context._agent!s}',
        # ]:
        #     self.etcd_client.delete_prefix(path.encode('utf-8'))
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

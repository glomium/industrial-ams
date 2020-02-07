#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import re
# import os

import grpc

from docker import errors as docker_errors
from google.protobuf.empty_pb2 import Empty

from .simulation import Runtime
from .proto import simulation_pb2
from .proto import simulation_pb2_grpc
from .proto import framework_pb2
from .proto import framework_pb2_grpc
from .utils.auth import permissions
from .utils.docker import Docker
from .utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, client, cfssl, namespace, args, credentials, threadpool, plugins):
        self.args = args
        self.cfssl = cfssl
        self.credentials = credentials
        self.threadpool = threadpool
        self.namespace = namespace

        self.docker = Docker(client, cfssl, namespace, args.namespace, args.simulation, plugins)

        self.RE_NAME = re.compile(r'^(%s_)?([\w]+)$' % self.namespace[0])

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
        return Empty()

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
        for service in self.docker.client.services.list(filters={'label': [f"iams.namespace={self.namespace}"]}):
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
            name = self.namespace[0] + '_' + request.name
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

    def __init__(self, threadpool):
        self.threadpool = threadpool
        self.simulations = None

    @permissions(has_groups=["root", "web"])
    def start(self, request, context):
        if self.simulations is not None:
            message = 'A simulation is currently running'
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, message)

        self.simulations = Runtime(self.threadpool, request)

        for x in range(100):

            yield simulation_pb2.SimulationLog(
                time=x,
            )

        logger.info("EXIT")
        self.simulations = None

    @permissions(has_agent=True)
    def schedule(self, request, context):
        # TODO
        pass

    @permissions(has_agent=True)
    def resume(self, request, context):
        # TODO
        pass

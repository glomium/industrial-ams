#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os
import re

from threading import Event

import grpc

from docker import errors as docker_errors
from google.protobuf.empty_pb2 import Empty

from .proto import framework_pb2
from .proto import framework_pb2_grpc
from .utils.arangodb import Arango
from .utils.auth import permissions
from .utils.docker import Docker
from .utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, client, cfssl, cloud, args, credentials, threadpool, plugins, runtests):
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

    # RPC
    @permissions(has_agent=True)
    def booted(self, request, context):
        logger.debug('booted called from %s', context._agent)
        self.del_booting(context._agent)
        return Empty()

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def agents(self, request, context):
        """
        """
        filters = list(request.filter) + [f"iams.namespace={self.args.namespace}"]
        for service in self.docker.client.services.list(filters={'label': filters}):
            image, version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)  # noqa
            yield framework_pb2.AgentData(
                name=service.name,
                image=image,
                version=version,
            )

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def update(self, request, context):
        logger.debug('Update called from %s', context._username)
        name = self.get_agent_name(context, request.name)

        try:
            created = self.docker.set_service(
                name,
                image=request.image,
                version=request.version,
                address=request.address,
                port=request.port,
                config=request.config,
                autostart=request.autostart,
                placement_constraints=request.constraints,
                placement_preferences=request.preferences,
            )

        except docker_errors.ImageNotFound:
            message = f'Could not find image {request.image}:{request.version}'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        except docker_errors.NotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{e!s}')

        if created:
            self.set_booting(name)

        return framework_pb2.AgentData(name=name)

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def create(self, request, context):
        logger.debug('create called from %s', context._username)

        regex = self.RE_NAME.match(request.name)
        if regex:
            name = self.args.namespace[0:4] + '_' + regex.group(2)
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
                placement_constraints=request.constraints,
                placement_preferences=request.preferences,
            )

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

        self.set_booting(name)
        self.create_callback(name)
        return framework_pb2.AgentData(name=name)

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
        self.docker.set_service(
            context._agent,
            update=True,
        )
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


FrameworkServicer.__doc__ = framework_pb2_grpc.FrameworkServicer.__doc__

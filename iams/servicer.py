#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from threading import Event

import grpc

from docker import errors as docker_errors
from google.protobuf.empty_pb2 import Empty

# from .proto import agent_pb2
# from .proto import df_pb2
from iams.exceptions import InvalidAgentName
from iams.proto import ca_pb2_grpc
from iams.proto import df_pb2_grpc
from iams.proto import framework_pb2
from iams.proto import framework_pb2_grpc
from iams.utils.auth import permissions
# from .utils.grpc import framework_channel
# from .utils.arangodb import Arango
from iams.utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, runtime, ca, df, threadpool):
        self.runtime = runtime
        self.ca = ca
        self.df = df

        self.threadpool = threadpool

        self.booting = set()
        self.event = Event()
        self.event.set()

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def update(self, request, context):
        logger.debug('Update called from %s', context._username)
        request.name = self.get_agent_name(context, request.name)

        try:
            created = self.runtime.update_agent(request)
            logger.debug("update_agent responded with created=%s", created)

        except docker_errors.ImageNotFound:
            message = f'Could not find image {request.image}:{request.version}'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        except docker_errors.NotFound as e:
            message = str(e)
            logger.debug(message)
            context.abort(grpc.StatusCode.NOT_FOUND, message)

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

        return framework_pb2.AgentData(name=request.name)

    # RPC
    @permissions(has_agent=True)
    def upgrade(self, request, context):
        logger.debug('upgrade called from %s', context._agent)
        self.runtime.update_agent(framework_pb2.AgentData(name=request.name), update=True)  # noqa
        return Empty()

    def get_agent_name(self, context, name):
        if context._agent is None and name is None:
            message = 'Need to give agent name in request'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if context._agent:
            return context._agent

        try:
            return self.runtime.get_valid_agent_name(name)
        except InvalidAgentName:
            message = 'Given an invalid agent name (%s) in request' % name
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

    # RPC
    @permissions(has_agent=True, has_groups=["root", "web"])
    def destroy(self, request, context):
        logger.debug('Destroy called from %s', context._username)
        try:
            request.name = self.get_agent_name(context, request.name)
            if self.runtime.delete_agent(request.name):
                return Empty()

        except docker_errors.NotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{e!s}')

    # RPC
    @permissions(has_agent=True)
    def sleep(self, request, context):
        logger.debug('sleep called from %s', context._agent)
        try:
            request.name = self.get_agent_name(context, request.name)
            if self.runtime.sleep_agent(request.name):
                return Empty()

        except docker_errors.NotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{e!s}')

    # RPC
    @permissions(has_agent=True)
    def wake(self, request, context):
        logger.debug('wake called from %s', context._agent)
        try:
            request.name = self.get_agent_name(context, request.name)
            if self.runtime.wake_agent(request.name):
                return Empty()

        except docker_errors.NotFound as e:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{e!s}')


class DirectoryFacilitatorServicer(df_pb2_grpc.DirectoryFacilitatorServicer):
    def __init__(self, df):
        self.df = df


class CertificateAuthorityServicer(ca_pb2_grpc.CertificateAuthorityServicer):
    def __init__(self, ca, runtime, threadpool):
        self.ca = ca
        self.runtime = runtime
        self.threadpool = threadpool

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
            self.threadpool.submit(
                self.runtime.update_agent,
                framework_pb2.AgentData(name=request.name),
                update=True,
            )
            return framework_pb2.RenewResponse()

        # generate private key and certificate and send it
        # the request is authenticated and origins from an agent, i.e it contains image and version
        certificate, private_key = self.ca.get_agent_certificate(
            request.name,
            image=context._image,
            version=context._version,
        )

        return framework_pb2.RenewResponse(
            private_key=private_key,
            certificate=certificate,
        )

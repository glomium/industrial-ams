#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
servicer
"""

import logging

from threading import Event

import grpc

from docker import errors as docker_errors
from google.protobuf.empty_pb2 import Empty

# from .proto import agent_pb2
# from .proto import df_pb2
from iams.exceptions import InvalidAgentName
from iams.proto import ca_pb2
from iams.proto import ca_pb2_grpc
from iams.proto import df_pb2_grpc
from iams.proto import framework_pb2
from iams.proto import framework_pb2_grpc
from iams.utils.grpc import credentials
# from .utils.grpc import framework_channel
# from .utils.arangodb import Arango
from iams.utils.ssl import validate_certificate


logger = logging.getLogger(__name__)


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):  # pylint: disable=empty-docstring

    def __init__(self, runtime, ca, df, threadpool):
        self.runtime = runtime
        self.ca = ca  # pylint: disable=invalid-name
        self.df = df  # pylint: disable=invalid-name

        self.threadpool = threadpool

        self.booting = set()
        self.event = Event()
        self.event.set()

    # RPC
    @credentials
    def update(self, request, context):
        """
        update
        """
        # pylint: disable=protected-access
        logger.debug('Update called from %s', context.credentials)
        request.name = self.get_agent_name(context, request.name)

        try:
            created = self.runtime.update_agent(request)
            logger.debug("update_agent responded with created=%s", created)

        except docker_errors.ImageNotFound:
            message = f'Could not find image {request.image}:{request.version}'
            logger.debug(message)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        except docker_errors.NotFound as exception:
            message = str(exception)
            logger.debug(message)
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        return framework_pb2.AgentData(name=request.name)

    @credentials
    def create(self, request, context):
        """
        create
        """
        # pylint: disable=protected-access
        logger.debug('create called from %s', context.credentials)
        raise NotImplementedError()

        # regex = self.RE_NAME.match(request.name)
        # if regex:
        #     request.name = self.args.namespace[0:4] + '_' + regex.group(2)
        # else:
        #     message = 'A name with starting with a letter, ending with an alphanumerical chars and ' \
        #               'only containing alphanumerical values and hyphens is required to define agents'
        #     logger.debug(message)
        #     context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        # if not request.image:
        #     message = 'An image is required to define agents'
        #     logger.debug(message)
        #     context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        # if not request.version:
        #     message = 'A version is required to define agents'
        #     logger.debug(message)
        #     context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        # try:
        #     self.runtime.update_agent(request)

        # except docker_errors.ImageNotFound:
        #     message = f'Could not find image {request.image}:{request.version}'
        #     logger.debug(message)
        #     context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        # except docker_errors.NotFound as exception:
        #     message = f'{exception!s}'
        #     logger.debug(message)
        #     context.abort(grpc.StatusCode.NOT_FOUND, message)
        # except ValueError as exception:
        #     message = f'{exception!s}'
        #     logger.debug(message)
        #     context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        # return framework_pb2.AgentData(name=request.name)

    @credentials
    def upgrade(self, request, context):
        """
        upgrade
        """
        # pylint: disable=protected-access
        logger.debug('upgrade called from %s', context.credentials)
        self.runtime.update_agent(framework_pb2.AgentData(name=request.name), update=True)  # noqa
        return Empty()

    def get_agent_name(self, context, name):  # pylint: disable=inconsistent-return-statements
        """
        get agent name
        """
        # pylint: disable=protected-access
        if context.credentials is None and name is None:
            message = 'Need to give agent name in request'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if name is None and context.credentials:
            return context.credentials

        try:
            return self.runtime.get_valid_agent_name(name)
        except InvalidAgentName:
            message = f'Given an invalid agent name ({name}) in request'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

    @credentials
    def destroy(self, request, context):  # pylint: disable=inconsistent-return-statements
        """
        destroy
        """
        # pylint: disable=protected-access
        logger.debug('Destroy called from %s', context.credentials)
        try:
            request.name = self.get_agent_name(context, request.name)
        except docker_errors.NotFound as exception:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{exception!s}')
        else:
            if self.runtime.delete_agent(request.name):
                return Empty()
            return Empty()

    @credentials
    def sleep(self, request, context):  # pylint: disable=inconsistent-return-statements
        """
        sleep
        """
        # pylint: disable=protected-access
        logger.debug('sleep called from %s', context.credentials)
        try:
            request.name = self.get_agent_name(context, request.name)
        except docker_errors.NotFound as exception:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{exception!s}')
        else:
            if self.runtime.sleep_agent(request.name):
                return Empty()
            return Empty()

    @credentials
    def wake(self, request, context):  # pylint: disable=inconsistent-return-statements
        """
        wake agent
        """
        # pylint: disable=protected-access
        logger.debug('wake called from %s', context.credentials)
        try:
            request.name = self.get_agent_name(context, request.name)
        except docker_errors.NotFound as exception:
            context.abort(grpc.StatusCode.NOT_FOUND, f'{exception!s}')
        else:
            if self.runtime.wake_agent(request.name):
                return Empty()
            return Empty()


class DirectoryFacilitatorServicer(df_pb2_grpc.DirectoryFacilitatorServicer):  # pylint: disable=empty-docstring
    def __init__(self, df):
        self.df = df  # pylint: disable=invalid-name


class CertificateAuthorityServicer(ca_pb2_grpc.CertificateAuthorityServicer):  # pylint: disable=empty-docstring
    def __init__(self, ca, runtime, threadpool):
        self.ca = ca  # pylint: disable=invalid-name
        self.runtime = runtime
        self.threadpool = threadpool

    @credentials(optional=True)
    def renew(self, request, context):

        if context.credentials is not None:  # pylint: disable=protected-access
            request.name = context.credentials  # pylint: disable=protected-access
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
        certificate, private_key = self.ca.get_agent_certificate(request.name)

        return ca_pb2.RenewResponse(  # pylint: disable=no-member
            private_key=private_key,
            certificate=certificate,
        )


CertificateAuthorityServicer.__doc__ = ca_pb2_grpc.CertificateAuthorityServicer.__doc__
DirectoryFacilitatorServicer.__doc__ = df_pb2_grpc.DirectoryFacilitatorServicer.__doc__
FrameworkServicer.__doc__ = framework_pb2_grpc.FrameworkServicer.__doc__

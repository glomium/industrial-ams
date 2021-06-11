#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.servicer
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

# import unittest
# from concurrent import futures

# import grpc

# from iams.ca import CFSSL
# from iams.proto import ca_pb2
# from iams.proto.ca_pb2_grpc import add_CertificateAuthorityServicer_to_server
# from iams.proto.df_pb2_grpc import add_DirectoryFacilitatorServicer_to_server
# from iams.proto.framework_pb2_grpc import add_FrameworkServicer_to_server
# from iams.servicer import CertificateAuthorityServicer
# from iams.servicer import DirectoryFacilitatorServicer
# from iams.servicer import FrameworkServicer
# from iams.stub import CAStub
from iams.tests.tests_server import ServerTestCase


class CertificateAuthorityServicerTest(ServerTestCase):  # pragma: no cover

    def test_get_credentials(self):
        """
        """


class DirectoryFacilitatorServicerTest(ServerTestCase):  # pragma: no cover

    def test_server(self):
        """
        with grpc.insecure_channel(f'localhost:{self.insecure_port}') as channel:
            stub = helloworld_pb2_grpc.GreeterStub(channel)
            response = stub.SayHello(helloworld_pb2.HelloRequest(name='Jack'))
        self.assertEqual(response.message, 'Hello, Jack!')
        """


class FrameworkServicerTest(ServerTestCase):  # pragma: no cover

    def test_server(self):
        """
        with grpc.insecure_channel(f'localhost:{self.insecure_port}') as channel:
            stub = helloworld_pb2_grpc.GreeterStub(channel)
            response = stub.SayHello(helloworld_pb2.HelloRequest(name='Jack'))
        self.assertEqual(response.message, 'Hello, Jack!')
        """

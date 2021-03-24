#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import grpc

from concurrent import futures

from iams.proto.ca_pb2_grpc import add_CertificateAuthorityServicer_to_server
from iams.proto.df_pb2_grpc import add_DirectoryFacilitatorServicer_to_server
from iams.proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from iams.servicer import CertificateAuthorityServicer
from iams.servicer import DirectoryFacilitatorServicer
from iams.servicer import FrameworkServicer
from iams.tests.ca import CA
from iams.tests.df import DF
from iams.tests.runtime import Runtime


class CertificateAuthorityServicerTest(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.threadpool = futures.ThreadPoolExecutor(max_workers=5)
        self.server = grpc.server(self.threadpool)
        # self.secure_port = self.server.add_insecure_port('[::]:0')
        self.insecure_port = self.server.add_insecure_port('[::]:0')
        add_CertificateAuthorityServicer_to_server(
            CertificateAuthorityServicer(CA(), Runtime(), self.threadpool),
            self.server,
        )
        self.server.start()

    def tearDown(self):
        self.server.stop(None)
        self.threadpool.shutdown()

    def test_server(self):
        pass
        # with grpc.insecure_channel(f'localhost:{self.insecure_port}') as channel:
        #     stub = helloworld_pb2_grpc.GreeterStub(channel)
        #     response = stub.SayHello(helloworld_pb2.HelloRequest(name='Jack'))
        # self.assertEqual(response.message, 'Hello, Jack!')


class DirectoryFacilitatorServicerTest(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.threadpool = futures.ThreadPoolExecutor(max_workers=5)
        self.server = grpc.server(self.threadpool)
        # self.secure_port = self.server.add_insecure_port('[::]:0')
        self.insecure_port = self.server.add_insecure_port('[::]:0')
        add_CertificateAuthorityServicer_to_server(
            CertificateAuthorityServicer(CA(), Runtime(), self.threadpool),
            self.server,
        )
        add_DirectoryFacilitatorServicer_to_server(
            DirectoryFacilitatorServicer(DF()),
            self.server,
        )
        self.server.start()

    def tearDown(self):
        self.server.stop(None)
        self.threadpool.shutdown()

    def test_server(self):
        pass
        # with grpc.insecure_channel(f'localhost:{self.insecure_port}') as channel:
        #     stub = helloworld_pb2_grpc.GreeterStub(channel)
        #     response = stub.SayHello(helloworld_pb2.HelloRequest(name='Jack'))
        # self.assertEqual(response.message, 'Hello, Jack!')


class FrameworkServicerTest(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        self.threadpool = futures.ThreadPoolExecutor(max_workers=5)
        self.server = grpc.server(self.threadpool)
        # self.secure_port = self.server.add_insecure_port('[::]:0')
        self.insecure_port = self.server.add_insecure_port('[::]:0')
        add_FrameworkServicer_to_server(
            FrameworkServicer(Runtime(), CA(), DF(), self.threadpool),
            self.server,
        )
        self.server.start()

    def tearDown(self):
        self.server.stop(None)
        self.threadpool.shutdown()

    def test_server(self):
        pass
        # with grpc.insecure_channel(f'localhost:{self.insecure_port}') as channel:
        #     stub = helloworld_pb2_grpc.GreeterStub(channel)
        #     response = stub.SayHello(helloworld_pb2.HelloRequest(name='Jack'))
        # self.assertEqual(response.message, 'Hello, Jack!')

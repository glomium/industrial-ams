#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unittests for iams.utils.grpc
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

from concurrent import futures
from pathlib import Path
import unittest

import grpc
from iams.ca import CFSSL
from iams.proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from iams.utils.grpc import Grpc
from iams.proto import framework_pb2
from iams.proto import framework_pb2_grpc
from iams.utils.grpc import credentials


cfssl = CFSSL("localhost:8888")
try:
    cfssl()
except Exception as exception:  # pylint: disable=broad-except # pragma: no cover
    SKIP = str(exception)
else:
    SKIP = None


class BaseServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.credentials = set()


class Servicer1(BaseServicer):

    @credentials(optional=True)
    def update(self, request, context):
        self.credentials = context.credentials
        return framework_pb2.AgentData(name="servicer1")


class Servicer2(BaseServicer):

    @credentials
    def update(self, request, context):
        self.credentials = context.credentials
        return framework_pb2.AgentData(name="servicer2")


class Context:
    credentials = set()


class InternalGrpcTest(unittest.TestCase):  # pragma: no cover
    def test_internal(self):
        servicer = Servicer2()
        response = servicer.update(framework_pb2.AgentRequest(), Context())
        self.assertEqual(response.name, "servicer2")  # pylint: disable=no-member


class InSecureGrpcTest(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        # pylint: disable=consider-using-with
        self.threadpool = futures.ThreadPoolExecutor(max_workers=1)
        self.grpc = Grpc("testname", None, secure=False)

    def tearDown(self):
        self.threadpool.shutdown()

    def test_servicer1(self):
        servicer = Servicer1()
        self.grpc(self.threadpool, insecure_port=0)
        self.grpc.add(
            add_FrameworkServicer_to_server,
            servicer,
        )
        with self.grpc as srv, srv.channel('localhost', port=srv.insecure_port, secure=False) as channel:
            self.assertIsNone(srv.port)
            self.assertNotEqual(srv.insecure_port, 0)
            stub = framework_pb2_grpc.FrameworkStub(channel)
            response = stub.update(framework_pb2.AgentRequest())
            self.assertEqual(response.name, "servicer1")
        self.assertEqual(set(), servicer.credentials)

    def test_servicer2(self):
        servicer = Servicer2()
        self.grpc(self.threadpool, insecure_port=0)
        self.grpc.add(
            add_FrameworkServicer_to_server,
            servicer,
        )
        with self.assertRaises(grpc.RpcError), self.grpc as srv, srv.channel('localhost', port=srv.insecure_port, secure=False) as channel:  # noqa
            self.assertIsNone(srv.port)
            self.assertNotEqual(srv.insecure_port, 0)
            stub = framework_pb2_grpc.FrameworkStub(channel)
            stub.update(framework_pb2.AgentRequest())
            try:
                stub.update(framework_pb2.AgentRequest())
            except grpc.RpcError as exception:
                self.assertEqual(exception.code(), grpc.StatusCode.UNAUTHENTICATED)  # pylint: disable=no-member
                raise exception


@unittest.skipIf(SKIP is not None, SKIP)
class SecureGrpcTest(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        # pylint: disable=consider-using-with
        self.threadpool = futures.ThreadPoolExecutor(max_workers=1)
        self.grpc = Grpc("testname", cfssl)

    def tearDown(self):
        self.threadpool.shutdown()

    def test_no_endpoint(self):
        self.grpc(self.threadpool, port=0)
        self.grpc.add(add_FrameworkServicer_to_server, Servicer1())
        with self.assertRaises(ValueError), self.grpc as srv, srv.channel(port=srv.port):
            pass

    def test_servicer1(self):
        servicer = Servicer1()
        self.grpc(self.threadpool, port=0)
        self.grpc.add(
            add_FrameworkServicer_to_server,
            servicer,
        )

        with self.grpc as srv, srv.channel('localhost', port=srv.port) as channel:
            self.assertIsNone(srv.insecure_port)
            self.assertNotEqual(srv.port, 0)
            stub = framework_pb2_grpc.FrameworkStub(channel)
            response = stub.update(framework_pb2.AgentRequest())
            self.assertEqual(response.name, "servicer1")
        self.assertEqual({"testname"}, servicer.credentials)

    def test_servicer2(self):
        servicer = Servicer2()
        self.grpc(self.threadpool, port=0)
        self.grpc.add(
            add_FrameworkServicer_to_server,
            servicer,
        )

        with self.grpc as srv, srv.channel('localhost', port=srv.port, proxy="localhost") as channel:
            self.assertIsNone(srv.insecure_port)
            self.assertNotEqual(srv.port, 0)
            stub = framework_pb2_grpc.FrameworkStub(channel)
            response = stub.update(framework_pb2.AgentRequest())
            self.assertEqual(response.name, "servicer2")
        self.assertEqual({"testname"}, servicer.credentials)


class SecretGrpcTest(unittest.TestCase):  # pragma: no cover

    def test_no_endpoint(self):
        Grpc("testname", secret_folder=Path("iams/tests/secrets"))

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from .proto import agent_pb2_grpc
from .proto import ca_pb2_grpc
from .proto import df_pb2_grpc
from .proto import framework_pb2_grpc
# from .utils.grpc import grpc_retry


logger = logging.getLogger(__name__)


class AgentStub(agent_pb2_grpc.AgentStub):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.connection_get = grpc_retry(self.connection_get)
        # self.ping = grpc_retry(self.ping)
        # self.service_get = grpc_retry(self.service_get)
        # self.simulation_continue = grpc_retry(self.simulation_continue)


class CAStub(ca_pb2_grpc.CertificateAuthorityStub):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DFStub(df_pb2_grpc.DirectoryFacilitatorStub):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class FrameworkStub(framework_pb2_grpc.FrameworkStub):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.agents = grpc_retry(self.agents)
        # self.booted = grpc_retry(self.booted)
        # self.create = grpc_retry(self.create)
        # self.destroy = grpc_retry(self.destroy)
        # self.images = grpc_retry(self.images)
        # self.sleep = grpc_retry(self.sleep)
        # self.upgrade = grpc_retry(self.upgrade)
        # self.update = grpc_retry(self.update)

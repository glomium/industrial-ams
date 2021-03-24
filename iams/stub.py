#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

# from functools import wraps

from iams.proto import agent_pb2_grpc
from iams.proto import ca_pb2_grpc
from iams.proto import df_pb2_grpc
from iams.proto import framework_pb2_grpc


logger = logging.getLogger(__name__)


# def grpc_retry(f, transactional=False, internal=1, aborted=3, unavailable=10, deadline_exceeded=3, *args, **kwargs):
#     retry_codes = {
#         grpc.StatusCode.INTERNAL: os.environ.get("GRPC_RETRY_INTERNAL", internal),
#         grpc.StatusCode.ABORTED: os.environ.get("GRPC_RETRY_ABORTED", aborted),
#         grpc.StatusCode.UNAVAILABLE: os.environ.get("GRPC_RETRY_UNAVAILABLE", unavailable),
#         grpc.StatusCode.DEADLINE_EXCEEDED: os.environ.get("GRPC_RETRY_DEADLINE_EXCEEDED", deadline_exceeded),
#     }
#     if isinstance(f, grpc.UnaryStreamMultiCallable):
#         @wraps(f)
#         def wrapper_stream(*args, **kwargs):
#             retries = 0
#             while True:
#                 try:
#                     for x in f(*args, **kwargs):
#                         yield x
#                     break
#                 except grpc.RpcError as e:
#                     code = e.code()
#                     max_retries = retry_codes.get(code, 0)
#                     retries += 1
#                     if retries > max_retries or transactional and code == grpc.StatusCode.ABORTED:
#                         raise
#                     sleep = min(0.01 * retries ** 3, 1.0)
#                     logger.debug("retrying failed request (%s) in %s seconds", code, sleep)
#                     time.sleep(sleep)
#         return wrapper_stream
#     if isinstance(f, grpc.UnaryUnaryMultiCallable):
#         @wraps(f)
#         def wrapper_unary(*args, **kwargs):
#             retries = 0
#             while True:
#                 try:
#                     return f(*args, **kwargs)
#                 except grpc.RpcError as e:
#                     code = e.code()
#                     max_retries = retry_codes.get(code, 0)
#                     retries += 1
#                     if retries > max_retries or transactional and code == grpc.StatusCode.ABORTED:
#                         raise
#                     sleep = min(0.01 * retries ** 3, 1.0)
#                     logger.debug("retrying failed request (%s) in %s seconds", code, sleep)
#                     time.sleep(sleep)
#         return wrapper_unary
#     return f


class AgentStub(agent_pb2_grpc.AgentStub):
    pass
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # self.connection_get = grpc_retry(self.connection_get)
    #     # self.ping = grpc_retry(self.ping)
    #     # self.service_get = grpc_retry(self.service_get)
    #     # self.simulation_continue = grpc_retry(self.simulation_continue)


class CAStub(ca_pb2_grpc.CertificateAuthorityStub):
    pass
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)


class DFStub(df_pb2_grpc.DirectoryFacilitatorStub):
    pass
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)


class FrameworkStub(framework_pb2_grpc.FrameworkStub):
    pass
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # self.agents = grpc_retry(self.agents)
    #     # self.booted = grpc_retry(self.booted)
    #     # self.create = grpc_retry(self.create)
    #     # self.destroy = grpc_retry(self.destroy)
    #     # self.images = grpc_retry(self.images)
    #     # self.sleep = grpc_retry(self.sleep)
    #     # self.upgrade = grpc_retry(self.upgrade)
    #     # self.update = grpc_retry(self.update)

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import os

from uuid import uuid1

import grpc
import msgpack

# from collections import defaultdict

from etcd3.client import Etcd3Client
# from etcd3.utils import increment_last_byte
from google.protobuf.empty_pb2 import Empty

from .constants import States
from .exceptions import EventNotFound
# from .rpc import agent_pb2 as agent
from .rpc import agent_pb2_grpc
from .rpc import framework_pb2_grpc
from .rpc import framework_pb2
from .rpc import simulation_pb2_grpc
from .rpc.agent_pb2 import ConnectionResponse
from .rpc.agent_pb2 import PingResponse
from .rpc.agent_pb2 import ServiceResponse
from .rpc.framework_pb2 import WakeAgent
from .rpc.simulation_pb2 import EventRegister
from .utils import agent_required
from .utils import framework_channel
from .utils import grpc_retry


logger = logging.getLogger(__name__)


class FrameworkStub(framework_pb2_grpc.FrameworkStub):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.agents = grpc_retry(self.agents)
        self.booted = grpc_retry(self.booted)
        self.create = grpc_retry(self.create)
        self.destroy = grpc_retry(self.destroy)
        self.images = grpc_retry(self.images)
        self.sleep = grpc_retry(self.sleep)
        self.upgrade = grpc_retry(self.upgrade)
        self.update = grpc_retry(self.update)

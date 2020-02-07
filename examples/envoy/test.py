#!/usr/bin/env python3

import grpc

from google.protobuf.empty_pb2 import Empty

from ams.server import FrameworkStub
from ams.utils import framework_channel


if __name__ == '__main__':
    print('client starting ...')

    with framework_channel("tasks.ams-ctrl", "127.0.0.1", 5005) as channel:
        stub = FrameworkStub(channel)
        response = stub.ping(Empty(), timeout=10)
        print('client done ... %s' % response)

#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import logging
import os

from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from time import sleep

import grpc

from .helper import get_logging_config


# class Runner(object):
#     pass


def execute_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-q', '--quiet',
        help="Be quiet",
        action="store_const",
        dest="loglevel",
        const=logging.WARNING,
        default=logging.INFO,
    )
    parser.add_argument(
        '-d', '--debug',
        help="Debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
    )
    parser.add_argument(
        '-p', '--port',
        help="Port",
        dest="port",
        type=int,
        default=80,
    )
    parser.add_argument(
        '--simulation',
        help="Run ams in simulation mode",
        dest='simulation',
        action='store_true',
        default=False,
    )

    args = parser.parse_args()

    dictConfig(get_logging_config(["iams"], args.loglevel))
    logger = logging.getLogger(__name__)

    assert os.environ.get('IAMS_HOST'), "Environment IAMS_HOST not set"
    assert os.environ.get('IAMS_CFSSL'), "Environment IAMS_CFSSL not set"

    # # dynamically load services from environment
    # logger.debug("loading services configuration")
    # self.services = {}
    # for key, data in os.environ.items():
    #     if key.startswith(self.PREFIX):
    #         # extract data from json
    #         label, path, config = json.loads(data)
    #         # dynamic load of plugin
    #         module_name, plugin_name = path.rsplit('.', 1)
    #         module = import_module(module_name)
    #         plugin = getattr(module, plugin_name)
    #         # add service
    #         logger.debug("loaded %s for label %s", path, label)
    #         self.services[label] = plugin(config)

    server = grpc.server(ThreadPoolExecutor())
    server.add_insecure_port('[::]:%s' % args.port)
    '''
    self.framework = FrameworkServicer(self, self.type, DockerClient())
    framework_pb2_grpc.add_FrameworkServicer_to_server(self.framework, self.server)
    '''
    if args.simulation:
        '''
        simulation_pb2_grpc.add_SimulationServicer_to_server(
            SimulationServicer(self),
            self.server,
        )
        '''
        pass
    server.start()

    # service running
    logger.debug("container manager running")
    try:
        while True:
            sleep(3600)
    except KeyboardInterrupt:
        pass

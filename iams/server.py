#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import datetime
import logging
import os

from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from time import sleep

import grpc

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from .cfssl import get_ca_public_key
from .cfssl import get_certificate
from .helper import get_logging_config
from .proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from .servicer import FrameworkServicer

"""
SSL-CN: "string" -> user
SSL-CN: "string:string:string" -> agent_name, image, version
"""


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
        '--rsa',
        help="RSA key length",
        dest="rsa",
        type=int,
        default=2096,
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

    server = grpc.server(ThreadPoolExecutor())
    add_FrameworkServicer_to_server(FrameworkServicer(
        args,
    ), server)

    assert os.environ.get('IAMS_HOST'), "Environment IAMS_HOST not set"

    if args.simulation is False:
        assert os.environ.get('IAMS_CFSSL'), "Environment IAMS_CFSSL not set"

        ca_public = get_ca_public_key()
        logger.debug('Public key: %s', ca_public)
        response = get_certificate('root', hosts=["localhost"])
        certificate = response["result"]["certificate"].encode()
        # certificate_request = response["result"]["certificate_request"].encode()
        private_key = response["result"]["private_key"].encode()

        cert = x509.load_pem_x509_certificate(certificate, default_backend())
        logger.debug("private key: %s", private_key)

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

        credentials = grpc.ssl_server_credentials(
            ((private_key, certificate),),
            root_certificates=ca_public,
            require_client_auth=True,
        )
        server.add_secure_port('[::]:%s' % args.port, credentials)
    else:
        server.add_insecure_port('[::]:%s' % args.port)
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
        if args.simulation is False:
            sleep((cert.not_valid_after - datetime.datetime.now()).total_seconds())
        else:
            while True:
                sleep(24 * 3600)
    except KeyboardInterrupt:
        pass

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

from .utils.cfssl import get_ca_public_key
from .utils.cfssl import get_certificate
from .helper import get_logging_config
from .proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from .servicer import FrameworkServicer

"""
SSL-CN: "string" -> user
SSL-CN: "string:string:string" -> agent_name, image, version
"""


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
        '--agent-port',
        help="Agent Port=443",
        dest="agent_port",
        type=int,
        default=443,
    )
    parser.add_argument(
        '--secure-port',
        help="Secure Port=443",
        dest="secure_port",
        type=int,
        default=443,
    )
    parser.add_argument(
        '--insecure-port',
        help="Insecure Port=80",
        dest="insecure_port",
        type=int,
        default=80,
    )
    parser.add_argument(
        '--rsa',
        help="RSA key length=4096",
        dest="rsa",
        type=int,
        default=4096,
    )
    parser.add_argument(
        '--simulation',
        help="Run ams in simulation mode",
        dest='simulation',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--namespace',
        help="docker stack namespace name (default: cloud)",
        dest='namespace',
        default="cloud",
    )

    args = parser.parse_args()

    dictConfig(get_logging_config(["iams"], args.loglevel))
    logger = logging.getLogger(__name__)

    assert os.environ.get('IAMS_HOST'), "Environment IAMS_HOST not set"
    assert os.environ.get('IAMS_CFSSL'), "Environment IAMS_CFSSL not set"

    plugins = {}

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

    threadpool = ThreadPoolExecutor()
    server = grpc.server(threadpool)

    # request CA's public key
    ca_public = get_ca_public_key()
    logger.debug('ca-public-key: %s', ca_public)

    # create certificate and private key from CA
    response = get_certificate('root', hosts=["localhost"], size=args.rsa)
    certificate = response["result"]["certificate"].encode()
    # certificate_request = response["result"]["certificate_request"].encode()
    private_key = response["result"]["private_key"].encode()
    logger.debug("iams-private-key: %s", private_key)

    # load certificate data (used to shutdown service after certificate became invalid)
    cert = x509.load_pem_x509_certificate(certificate, default_backend())
    tol = (cert.not_valid_after - datetime.datetime.now()).total_seconds()

    credentials = grpc.ssl_server_credentials(
        ((private_key, certificate),),
        root_certificates=ca_public,
        require_client_auth=True,
    )
    channel_credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_public,
        private_key=private_key,
        certificate_chain=certificate,
    )

    server.add_secure_port('[::]:%s' % args.secure_port, credentials)
    server.add_insecure_port('[::]:%s' % args.insecure_port)

    add_FrameworkServicer_to_server(FrameworkServicer(
        args,
        channel_credentials,
        threadpool,
        plugins,
    ), server)

    if args.simulation is True:
        '''
        simulation_pb2_grpc.add_SimulationServicer_to_server(
            SimulationServicer(self),
            self.server,
        )
        '''
        pass
    server.start()

    # service running
    tol -= 60
    logger.info("container manager running for %s seconds", tol)
    try:
        sleep(tol)
    except ValueError:
        logger.error("certificate livetime less then 60 seconds")
    except KeyboardInterrupt:
        pass

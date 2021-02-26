#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import datetime
import logging
import os

from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from threading import Event

import grpc

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from .ca import CFSSL
from .constants import AGENT_PORT
from .df import ArangoDF
from .exceptions import SkipPlugin
from .helper import get_logging_config
from .proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from .runtime import DockerSwarmRuntime
from .servicer import FrameworkServicer
from .utils.cfssl import CFSSL as CFSSL2
from .utils.plugins import get_plugins


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
        'cfssl',
        help="http interface of cfssl service",
        default="tasks.cfssl:8888",
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
        help="RSA key length",
        dest="rsa",
        type=int,
        default=4096,
    )
    parser.add_argument(
        '--hosts',
        help="Comma seperated list of hostnames, which are used Hosts used in certificate creation",
        dest="hosts",
        default=os.environ.get('IAMS_HOSTS', None),
    )
    parser.add_argument(
        '--namespace',
        help="stack namespace (default: simulation or production)",
        dest='namespace',
        default=os.environ.get('IAMS_NAMESPACE', "prod"),
    )

    args = parser.parse_args()
    stop = Event()
    dictConfig(get_logging_config(["iams"], args.loglevel))
    logger = logging.getLogger(__name__)

    logger.info("IAMS namespace: %s", args.namespace)

    if args.hosts:
        args.hosts = ["127.0.0.1", "localhost"] + args.hosts.split(',')
    else:
        args.hosts = ["127.0.0.1", "localhost"]

    cfssl = CFSSL2(args.cfssl, args.rsa, args.hosts)
    ca = CFSSL()
    df = ArangoDF()
    runtime = DockerSwarmRuntime(ca, cfssl)

    # dynamically load services from environment
    for cls in get_plugins():
        try:
            logger.info("Loaded plugin %s (usage label: %s)", cls.__qualname__, cls.label())
            runtime.register_plugin(cls(
                namespace=runtime.namespace,
                simulation=False,
            ))
        except SkipPlugin:
            logger.info("Skipped plugin %s", cls.__qualname__)
        except Exception:
            logger.exception("Error loading plugin %s", cls.__qualname__)
            continue

    threadpool = ThreadPoolExecutor()
    server = grpc.server(threadpool)

    logger.info("Generating certificates")
    response = cfssl.get_certificate(runtime.servername, hosts=[runtime.servername], groups=["root"])

    certificate = response["result"]["certificate"].encode()
    private_key = response["result"]["private_key"].encode()

    # load certificate data (used to shutdown service after certificate became invalid)
    cert = x509.load_pem_x509_certificate(certificate, default_backend())

    credentials = grpc.ssl_server_credentials(
        ((private_key, certificate),),
        root_certificates=cfssl.ca,
        require_client_auth=True,
    )
    # channel_credentials = grpc.ssl_channel_credentials(
    #     root_certificates=cfssl.ca,
    #     private_key=private_key,
    #     certificate_chain=certificate,
    # )

    logger.debug("Open server on ports %s and %s", AGENT_PORT, args.insecure_port)
    server.add_insecure_port('[::]:%s' % args.insecure_port)
    server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)

    add_FrameworkServicer_to_server(FrameworkServicer(runtime, ca, df, threadpool), server)

    server.start()

    # service running
    logger.info("container manager running")
    try:
        while not stop.is_set():
            eta = cert.not_valid_after - datetime.datetime.now()
            logger.debug("certificate valid for %s days", eta.days)

            if eta.days > 1:
                stop.wait(86400)
            else:
                if runtime.container:
                    logger.debug("restart container")
                    runtime.container.reload()
                    runtime.container.restart()
                else:
                    break
                stop.wait(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    execute_command_line()

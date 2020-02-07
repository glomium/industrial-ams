#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import datetime
import logging
import os

from socket import gethostname
from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from time import sleep

import docker
import grpc

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from .constants import AGENT_PORT
from .exceptions import SkipPlugin
from .helper import get_logging_config
from .proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from .proto.simulation_pb2_grpc import add_SimulationServicer_to_server
from .servicer import FrameworkServicer
from .servicer import SimulationServicer
from .utils.cfssl import CFSSL
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
    )
    parser.add_argument(
        '--hosts',
        help="Comma seperated list of hostnames, which are used Hosts used in certificate creation",
        dest="hosts",
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
        help="stack namespace (default: simulation or production)",
        dest='namespace',
    )

    args = parser.parse_args()

    dictConfig(get_logging_config(["iams"], args.loglevel))
    logger = logging.getLogger(__name__)

    client = docker.DockerClient()
    try:
        container = client.containers.get(gethostname())
        namespace = container.attrs["Config"]["Labels"]["com.docker.stack.namespace"]
        logger.info("got namespace %s from docker", namespace)
        servername = container.attrs["Config"]["Labels"]["com.docker.swarm.service.name"]
        servername = "tasks." + servername[len(namespace) + 1:]
        logger.info("got servername %s from docker", servername)
    except docker.errors.NotFound:
        container = None
        namespace = "undefined"
        servername = "localhost"
        logger.warning("Could not connect to docker container - please start iams-server as a docker-swarm service")

    # read variables from environment
    if not args.namespace:
        args.namespace = os.environ.get('IAMS_NAMESPACE', None)
    if not args.hosts:
        args.hosts = os.environ.get('IAMS_HOSTS', None)

    # manipulate user inputs
    if not args.namespace:
        if args.simulation:
            args.namespace = "simulation"
        else:
            args.namespace = "production"
        logger.info("setting namespace to %s", args.namespace)
    else:
        logger.info("reading namespace - %s", args.namespace)

    if not args.rsa or args.rsa < 2048:
        if args.simulation:
            args.rsa = 2048
        else:
            args.rsa = 4096
        logger.info("setting rsa key size to %s", args.rsa)
    else:
        logger.info("reading rsa key size - %s", args.rsa)

    if args.hosts:
        args.hosts = ["127.0.0.1", "localhost"] + args.hosts.split(',')
    else:
        args.hosts = ["127.0.0.1", "localhost"]

    # dynamically load services from environment
    plugins = []
    for cls in get_plugins():
        try:
            plugins.append(cls(
                namespace=args.namespace,
                simulation=args.simulation,
            ))
        except SkipPlugin:
            continue
        except Exception:
            logger.exception("Error loading plugin %r", cls)
            continue

    threadpool = ThreadPoolExecutor()
    server = grpc.server(threadpool)

    logger.info("Generating certificates")
    cfssl = CFSSL(args.cfssl, args.rsa, args.hosts)
    response = cfssl.get_certificate(servername, hosts=[servername], groups=["root"])
    certificate = response["result"]["certificate"].encode()
    private_key = response["result"]["private_key"].encode()

    # load certificate data (used to shutdown service after certificate became invalid)
    cert = x509.load_pem_x509_certificate(certificate, default_backend())

    credentials = grpc.ssl_server_credentials(
        ((private_key, certificate),),
        root_certificates=cfssl.ca,
        require_client_auth=True,
    )
    channel_credentials = grpc.ssl_channel_credentials(
        root_certificates=cfssl.ca,
        private_key=private_key,
        certificate_chain=certificate,
    )

    server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)
    server.add_insecure_port('[::]:%s' % args.insecure_port)

    add_FrameworkServicer_to_server(FrameworkServicer(
        client,
        cfssl,
        namespace,
        args,
        channel_credentials,
        threadpool,
        plugins,
    ), server)

    if args.simulation is True:
        add_SimulationServicer_to_server(
            SimulationServicer(threadpool),
            server,
        )
    server.start()

    # service running
    logger.info("container manager running")
    try:
        while True:
            eta = cert.not_valid_after - datetime.datetime.now()
            logger.debug("certificate valid for %s days", eta.days)

            if eta.days > 1:
                if container is not None and not args.simulation:
                    # TODO update certificates from apps?
                    pass
                sleep(86400.0)
            else:
                if container:
                    logger.debug("restart container")
                    container.reload()
                    container.restart()
                else:
                    break
                sleep(3600)
    except KeyboardInterrupt:
        pass

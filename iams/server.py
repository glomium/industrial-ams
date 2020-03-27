#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import datetime
import logging
import os

from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from socket import gethostname
from threading import Event

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
    stop = Event()
    dictConfig(get_logging_config(["iams"], args.loglevel))
    logger = logging.getLogger(__name__)

    client = docker.DockerClient()
    try:
        container = client.containers.get(gethostname())
        if "com.docker.stack.namespace" in container.attrs["Config"]["Labels"]:
            namespace = container.attrs["Config"]["Labels"]["com.docker.stack.namespace"]
            logger.info("got namespace %s from docker", namespace)
            servername = container.attrs["Config"]["Labels"]["com.docker.swarm.service.name"]
            servername = "tasks." + servername[len(namespace) + 1:]
            logger.info("got servername %s from docker", servername)
            cloudless = False
        elif "com.docker.compose.project" in container.attrs["Config"]["Labels"]:
            namespace = container.attrs["Config"]["Labels"]["com.docker.compose.project"]
            logger.info("got namespace %s from docker", namespace)
            servername = container.attrs["Config"]["Labels"]["com.docker.compose.service"]
            logger.info("got servername %s from docker", servername)
            cloudless = False
        else:
            namespace = "undefined"
            servername = "localhost"
            logger.warning("Could not read namespace or servername labels - start iams-server with docker-swarm")
            cloudless = True
    except docker.errors.NotFound:
        container = None
        namespace = "undefined"
        servername = "localhost"
        logger.warning("Could not connect to docker container - start iams-server as a docker-swarm service")
        cloudless = True

    # read variables from environment
    if not args.namespace:
        args.namespace = os.environ.get('IAMS_NAMESPACE', None)
    if not args.hosts:
        args.hosts = os.environ.get('IAMS_HOSTS', None)

    # manipulate user inputs
    if not args.namespace:
        if args.simulation:
            args.namespace = "sim"
        else:
            args.namespace = "prod"
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
            logger.info("Loaded plugin %s (usage label: %s)", cls.__qualname__, cls.label)
        except SkipPlugin:
            logger.info("Skipped plugin %s", cls.__qualname__)
        except Exception:
            logger.exception("Error loading plugin %s", cls.__qualname__)
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

    server.add_insecure_port('[::]:%s' % args.insecure_port)
    if cloudless:
        logger.debug("Open server on port %s", args.insecure_port)
    else:
        logger.debug("Open server on ports %s and %s", AGENT_PORT, args.insecure_port)
        server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)

    servicer = FrameworkServicer(
        client,
        cfssl,
        servername,
        namespace,
        args,
        channel_credentials,
        threadpool,
        plugins,
    )
    add_FrameworkServicer_to_server(servicer, server)

    if args.simulation is True:
        add_SimulationServicer_to_server(
            SimulationServicer(servicer, stop),
            server,
        )
    server.start()

    # service running
    logger.info("container manager running")
    try:
        while not stop.is_set():
            eta = cert.not_valid_after - datetime.datetime.now()
            logger.debug("certificate valid for %s days", eta.days)

            if eta.days > 1:
                # The following block can be used for maintenance tasks
                if container is not None and not args.simulation:
                    pass
                stop.wait(86400)
            else:
                if container:
                    logger.debug("restart container")
                    container.reload()
                    container.restart()
                else:
                    break
                stop.wait(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    execute_command_line()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from iams.ca import CFSSL
from iams.constants import AGENT_PORT
from iams.df import ArangoDF
from iams.exceptions import SkipPlugin
from iams.helper import get_logging_config
from iams.proto.ca_pb2_grpc import add_CertificateAuthorityServicer_to_server
from iams.proto.df_pb2_grpc import add_DirectoryFacilitatorServicer_to_server
from iams.proto.framework_pb2_grpc import add_FrameworkServicer_to_server
from iams.runtime import DockerSwarmRuntime
from iams.servicer import CertificateAuthorityServicer
from iams.servicer import DirectoryFacilitatorServicer
from iams.servicer import FrameworkServicer
from iams.utils.plugins import get_plugins


logger = logging.getLogger(__name__)


def parse_command_line(argv=None):
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

    return parser.parse_args()


def main(args):
    dictConfig(get_logging_config(["iams"], args.loglevel))

    logger.info("IAMS namespace: %s", args.namespace)

    if args.hosts:
        args.hosts = args.hosts.split(',')
    else:
        args.host = []

    # init and configure certificate authority
    ca = CFSSL(args.cfssl, args.hosts, args.rsa)
    ca()
    # init and configure directory facilitator
    df = ArangoDF()
    df()
    # init and configure runtime
    runtime = DockerSwarmRuntime(ca)
    runtime()

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

    logger.info("Generating certificates for root:%s", runtime.servername)
    certificate, private_key = ca.get_service_certificate("root", hosts=[runtime.servername])
    credentials = grpc.ssl_server_credentials(
        ((private_key, certificate),),
        root_certificates=ca.get_root_ca(),
        require_client_auth=True,
    )
    # channel_credentials = grpc.ssl_channel_credentials(
    #     root_certificates=cfssl.ca,
    #     private_key=private_key,
    #     certificate_chain=certificate,
    # )
    # load certificate data (used to shutdown service after certificate became invalid)
    cert = x509.load_pem_x509_certificate(certificate, default_backend())

    logger.debug("Open server on ports %s and %s", AGENT_PORT, args.insecure_port)
    server.add_insecure_port('[::]:%s' % args.insecure_port)
    server.add_secure_port(f'[::]:{AGENT_PORT}', credentials)

    add_CertificateAuthorityServicer_to_server(CertificateAuthorityServicer(ca, runtime, threadpool), server)
    add_DirectoryFacilitatorServicer_to_server(DirectoryFacilitatorServicer(df), server)
    add_FrameworkServicer_to_server(FrameworkServicer(runtime, ca, df, threadpool), server)

    server.start()

    # service running
    logger.info("container manager running")
    try:
        while True:
            eta = cert.not_valid_after - datetime.datetime.now()
            logger.debug("certificate valid for %s days", eta.days)

            if eta.days > 1:
                sleep(86400)
                continue
            if runtime.container:
                logger.debug("restart container")
                runtime.container.reload()
                runtime.container.restart()
            break
    except KeyboardInterrupt:
        pass


def execute_command_line():  # pragma: no cover
    main(parse_command_line())


if __name__ == "__main__":  # pragma: no cover
    main(parse_command_line())

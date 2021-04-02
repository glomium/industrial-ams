#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams server
"""

from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from time import sleep
import argparse
import datetime
import logging
import os

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from iams.ca import CFSSL
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
from iams.utils.grpc import Grpc
from iams.utils.plugins import get_plugins


logger = logging.getLogger(__name__)


def parse_command_line(argv=None):
    """
    Command line parser
    """
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

    args = parser.parse_args(argv)

    if args.hosts:
        args.hosts = args.hosts.split(',')
    else:
        args.host = []

    return args


class Server:
    """
    Iams Server
    """

    def __init__(self, args):
        self.args = args

    def __call__(self, ca=None, df=None, runtime=None):

        if ca is None:
            ca = CFSSL(self.args.cfssl, self.args.hosts)
        ca()

        if df is None:
            df = ArangoDF()
        df()

        if runtime is None:
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
            except Exception:  # pylint: disable=broad-except
                logger.exception("Error loading plugin %s", cls.__qualname__)
                continue

        server = Grpc(runtime.servername, ca)
        with ThreadPoolExecutor() as executor:
            server.server(executor)
            server.add(add_CertificateAuthorityServicer_to_server, CertificateAuthorityServicer(ca, runtime, executor))
            server.add(add_DirectoryFacilitatorServicer_to_server, DirectoryFacilitatorServicer(df))
            server.add(add_FrameworkServicer_to_server, FrameworkServicer(runtime, ca, df, executor))

            # load certificate data (used to shutdown service after certificate became invalid)
            cert = x509.load_pem_x509_certificate(server.certificate, default_backend())

            with server:
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
    """
    Execute command line
    """
    args = parse_command_line()
    dictConfig(get_logging_config(["iams"], args.loglevel))
    server = Server(args)
    server()


if __name__ == "__main__":  # pragma: no cover
    execute_command_line()

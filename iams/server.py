#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iams server
"""

from concurrent.futures import ThreadPoolExecutor
from logging.config import dictConfig
from time import sleep
import argparse
import logging
import os

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
    args.hosts = args.hosts.split(',') if args.hosts else []

    return args


class Server:
    """
    Iams Server
    """

    def __init__(self, args, ca=None, df=None, runtime=None):
        self.args = args
        self.ca = ca or CFSSL(self.args.cfssl, self.args.hosts)
        self.df = df or ArangoDF()
        self.runtime = runtime or DockerSwarmRuntime(self.ca)
        self.server = None

    def __call__(self, executor, secure=True):
        self.ca()
        self.df()
        self.runtime()
        self.get_plugins()

        hostname, port = self.runtime.get_address()
        self.server = Grpc(hostname, self.ca, secure=secure)

        self.server(executor, port=port, insecure_port=self.args.insecure_port)
        self.server.add(
            add_CertificateAuthorityServicer_to_server,
            CertificateAuthorityServicer(self.ca, self.runtime, executor),
        )
        self.server.add(
            add_DirectoryFacilitatorServicer_to_server,
            DirectoryFacilitatorServicer(self.df),
        )
        self.server.add(
            add_FrameworkServicer_to_server,
            FrameworkServicer(self.runtime, self.ca, self.df, executor),
        )
        return self.server

    def update_certificates(self):
        """
        updates certificates from agents and services that expire within two days
        """
        # logger.info("Checking for agents and services that require the update of a certificate")
        # logger.warning("%s.update_certificates is not implemented yet", self.__class__.__qualname__)

    def get_plugins(self):
        """
        dynamically load services from environment
        """
        for cls in get_plugins():
            try:
                logger.info("Loaded plugin %s (usage label: %s)", cls.__qualname__, cls.label())
                self.runtime.register_plugin(cls(
                    namespace=self.runtime.get_namespace(),
                    simulation=False,
                ))
            except SkipPlugin:
                logger.info("Skipped plugin %s", cls.__qualname__)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Error loading plugin %s", cls.__qualname__)
                continue


def execute_command_line():  # pragma: no cover
    """
    Execute command line
    """
    args = parse_command_line()
    dictConfig(get_logging_config(["iams"], args.loglevel))
    server = Server(args)

    with ThreadPoolExecutor() as executor, server(executor) as grpc_server:
        try:
            while True:
                expire = grpc_server.certificate_expire()
                logger.debug("Server certificate valid for %s days", expire.days)

                server.update_certificates()

                if expire.days > 1:
                    sleep(86400)
                    continue
                if hasattr(server.runtime, 'container'):
                    logger.debug("restart container")
                    server.runtime.container.reload()
                    server.runtime.container.restart()
                break
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":  # pragma: no cover
    execute_command_line()

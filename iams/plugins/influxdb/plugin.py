#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...exceptions import SkipPlugin
from ...interface import Plugin


logger = logging.getLogger(__name__)


class InfluxDB(Plugin):
    """
    INFLUXDB_HOST and INFLUXDB_DATABASE needs to be set as environment variables or the plugin wont load
    Adds INFLUXDB_HOST and INFLUXDB_DATABASE to the agents environment variabled
    Adds the agent to the network {stack-namespace}_influxdb
    """

    @property
    def label(self):
        return "iams.plugins.influxdb"

    def __init__(self, **kwargs):
        self.host = os.environ.get('INFLUXDB_HOST', None)
        if self.host is None:
            logger.debug("INFLUXDB_HOST is not defined - skip plugin")
            raise SkipPlugin
        self.database = os.environ.get('INFLUXDB_DATABASE', None)
        if self.database is None:
            logger.info("INFLUXDB_DATABASE is not defined - skip plugin")
            raise SkipPlugin

    def get_networks(self, **kwargs):
        return ['%s_influxdb' % self.namespace]

    def get_env(self, **kwargs):
        return {
            'INFLUXDB_HOST': self.host,
            'INFLUXDB_DATABASE': self.database,
        }

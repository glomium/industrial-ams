#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...exceptions import SkipPlugin
from ...interface import Plugin


logger = logging.getLogger(__name__)


class InfluxDB(Plugin):
    label = "iams.plugins.influxdb"

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
            'INFLUXDB_HOST': "tasks.influxdb",
        }

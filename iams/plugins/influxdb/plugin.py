#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...exceptions import SkipPlugin
from ...interface import Plugin


logger = logging.getLogger(__name__)


class InfluxDB(Plugin):

    def __init__(self, **kwargs):
        self.host = os.environ.get('INFLUXDB_HOST', "tasks.influxdb")
        self.database = os.environ.get('INFLUXDB_DATABASE', None)
        if self.database is None:
            logger.error("INFLUXDB_DATABASE is not defined - skip plugin")
            raise SkipPlugin

    def get_networks(self, **kwargs):
        return ['%s_influxdb' % self.namespace]

    def get_kwargs(self, name, image, version, config):
        return {"name": config}

    def get_env(self, name):
        return {
            'INFLUXDB_HOST': "tasks.influxdb",
            'INFLUXDB_TAG': f"ams.image.{name}",
        }

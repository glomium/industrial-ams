#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class InfluxDB(Plugin):

    def get_networks(self, **kwargs):
        return ['cloud_influxdb']

    def get_kwargs(self, config):
        return {"name": config}

    def get_env(self, name):
        return {
            'INFLUXDB_HOST': "tasks.influxdb",
            'INFLUXDB_TAG': f"ams.image.{name}",
        }

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class InfluxDB(Plugin):

    def __init__(self):
        pass

    def call__(self, config, **kwargs):
        logger.debug("calling %s plugin with config %s", self.__class__.__name__, config)
        networks = set(['cloud_influxdb'])
        env = {
            'INFLUXDB_HOST': "tasks.influxdb",
            'INFLUXDB_TAG': "ams.image.%s" % config,
        }
        return networks, env

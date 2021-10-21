#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
InfluxDB plugin
"""

import logging
import os

from iams.exceptions import SkipPlugin
from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class InfluxDB(Plugin):
    """
    INFLUX_BUCKET, INFLUX_HOST, INFLUX_ORG and INFLUX_TOKEN need to be set as environment variables
    otherwise the plugin will not load
    Adds these environmental variables to the agents environment variables
    Adds the agent to the network {stack-namespace}_influxdb
    """
    # pylint: disable=arguments-differ

    @classmethod
    def label(cls):
        return "iams.plugins.influxdb"

    def __init__(self, **kwargs):
        self.bucket = os.environ.get('INFLUX_BUCKET', None)
        self.host = os.environ.get('INFLUX_HOST', None)
        self.org = os.environ.get('INFLUX_ORG', None)
        self.token = os.environ.get('INFLUX_TOKEN', None)

        if self.bucket is None:
            logger.debug("INFLUX_BUCKET is not defined - skip plugin")
            raise SkipPlugin

        if self.host is None:
            logger.info("INFLUX_HOST is not defined - skip plugin")
            raise SkipPlugin

        if self.org is None:
            logger.info("INFLUX_ORG is not defined - skip plugin")
            raise SkipPlugin

        if self.token is None:
            logger.info("INFLUX_TOKEN is not defined - skip plugin")
            raise SkipPlugin

        super().__init__(**kwargs)

    def get_networks(self, **kwargs):
        return [f'{self.namespace}_influxdb']

    def get_env(self, **kwargs):
        return {
            'INFLUX_HOST': self.host,
            'INFLUX_BUCKET': self.bucket,
            'INFLUX_ORG': self.org,
            'INFLUX_TOKEN': self.token,
        }

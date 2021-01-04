#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from iams.exceptions import SkipPlugin
from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class Mqtt(Plugin):

    @classmethod
    def label(cls):
        return "iams.plugins.mqtt"

    def __init__(self, **kwargs):
        self.host = os.environ.get('MQTT_HOST', None)
        if self.host is None:
            logger.debug("MQTT_HOST is not defined - skip plugin")
            raise SkipPlugin
        super().__init__(**kwargs)

    def get_networks(self, **kwargs):
        return ['%s_mqtt' % self.namespace]

    def get_kwargs(self, name, image, version, config):
        return {"name": name.split('_', 1)[1]}

    def get_env(self, name):
        return {
            'MQTT_HOST': self.host,
            'MQTT_TOPIC': f"agents/{name}",
        }
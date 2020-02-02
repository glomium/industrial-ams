#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Fluentd(Plugin):

    def __init__(self):
        pass

    def call(self, config, **kwargs):
        logger.debug("calling %s plugin with config %s", self.__class__.__name__, config)
        networks = set(['cloud_fluentd'])
        env = {
            'FLUENTD_HOST': "tasks.fluentd",
            'FLUENTD_TAG': "ams.image.%s" % config,
        }
        return networks, env

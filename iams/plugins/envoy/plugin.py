#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Envoy(Plugin):

    def __init__(self, config):
        pass

    def __call__(self, config, **kwargs):
        logger.debug("calling %s plugin with config %s", self.__class__.__name__, config)
        networks = set(['cloud_envoy'])
        env = {}
        return networks, env

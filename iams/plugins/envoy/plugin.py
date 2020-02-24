#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Envoy(Plugin):
    label = "iams.plugin.envoy"

    def get_networks(self, **kwargs):
        return ['%s_envoy' % self.namespace]

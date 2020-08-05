#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class Envoy(Plugin):

    @classmethod
    def label(cls):
        return "iams.plugins.envoy"

    def get_networks(self, **kwargs):
        return ['%s_envoy' % self.namespace]

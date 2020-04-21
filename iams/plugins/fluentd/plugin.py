#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...exceptions import SkipPlugin
from ...interface import Plugin


logger = logging.getLogger(__name__)


class Fluentd(Plugin):

    def label():
        return "iams.plugins.fluentd"

    def __init__(self, **kwargs):
        self.host = os.environ.get('FLUENTD_HOST', None)
        if self.host is None:
            logger.debug("FLUENTD_HOST is not defined - skip plugin")
            raise SkipPlugin
        super().__init__(**kwargs)

    def get_networks(self, **kwargs):
        return ['%s_fluentd' % self.namespace]

    def get_kwargs(self, name, image, version, config):
        return {"name": name.split('_', 1)[1]}

    def get_env(self, name):
        return {
            'FLUENTD_HOST': self.host,
            'FLUENTD_TAG': f"iams.agent.{name}",
        }

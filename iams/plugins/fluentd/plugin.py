#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os

from iams.exceptions import SkipPlugin
from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class Fluentd(Plugin):

    @classmethod
    def label(cls):
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

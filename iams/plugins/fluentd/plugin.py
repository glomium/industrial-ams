#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Fluentd(Plugin):
    label = "iams.plugin.fluentd"

    def get_networks(self, **kwargs):
        return ['%s_fluentd' % self.namespace]

    def get_kwargs(self, name, image, version, config):
        return {"name": config}

    def get_env(self, name):
        return {
            'FLUENTD_HOST': "tasks.fluentd",
            'FLUENTD_TAG': f"ams.image.{name}",
        }

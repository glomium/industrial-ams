#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Fluentd(Plugin):

    def get_networks(self, **kwargs):
        return ['cloud_envoy']

    def get_kwargs(self, name, image, version, config):
        return {"name": config}

    def get_env(self, name):
        return {
            'FLUENTD_HOST': "tasks.fluentd",
            'FLUENTD_TAG': f"ams.image.{name}",
        }

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Envoy(Plugin):

    def __init__(self):
        pass

    def get_networks(self, **kwargs):
        return ['cloud_envoy']

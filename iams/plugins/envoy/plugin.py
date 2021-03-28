#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envoy
"""

import logging

from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class Envoy(Plugin):
    """
    envoy
    """

    @classmethod
    def label(cls):
        return "iams.plugins.envoy"

    def get_networks(self, **kwargs):
        return ['%s_envoy' % self.namespace]

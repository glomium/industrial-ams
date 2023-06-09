#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mqtt
"""

import logging
import os

from iams.exceptions import SkipPlugin
from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class Zeebe(Plugin):
    """
    Zeebe
    """
    # pylint: disable=arguments-differ

    @classmethod
    def label(cls):
        return "iams.plugins.zeebe"

    def __init__(self, **kwargs):
        self.host = os.environ.get('ZEEBE_HOST', None)
        if self.host is None:
            logger.debug("ZEEBE_HOST is not defined - skip plugin")
            raise SkipPlugin
        super().__init__(**kwargs)

    def get_networks(self, **kwargs):
        return [f'{self.namespace}_zeebe']

    def get_kwargs(self, name, image, version, config):
        return {"name": name.split('_', 1)[1]}

    def get_env(self, name):
        return {
            'ZEEBE_HOST': self.host,
            'ZEEBE_NAME': name,
        }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arangodb
"""

import logging
import os

from iams.interfaces.plugin import Plugin
from iams.utils.arangodb import get_credentials


logger = logging.getLogger(__name__)


class Arango(Plugin):
    """
    Arangodb
    """

    @classmethod
    def label(cls):
        return "iams.plugins.arango"

    def get_networks(self, **kwargs):
        return [f'{self.namespace}_arango']

    def get_env(self, **kwargs):
        database, unused, password = get_credentials(self.namespace)
        # username = database
        username = "root"
        password = unused

        logger.debug("arango-settings: %s:%s@%s", database, password, username)
        return {
            "ARANGO_HOSTS": os.environ.get("IAMS_ARANGO_HOSTS", "http://tasks.arangodb:8529"),
            "ARANGO_DATABASE": database,
            "ARANGO_USERNAME": username,
            "ARANGO_PASSWORD": password,
        }

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...interface import Plugin
from ...utils.arangodb import get_credentials


logger = logging.getLogger(__name__)


class Arango(Plugin):

    def label():
        return "iams.plugins.arango"

    def get_networks(self, **kwargs):
        return ['%s_arango' % self.namespace]

    def get_env(self, **kwargs):
        database, unused, password = get_credentials(self.namespace)
        return {
            "ARANGO_HOSTS": os.environ.get("IAMS_ARANGO_HOSTS", "http://tasks.arango:8529"),
            "ARANGO_DATABASE": database,
            "ARANGO_USERNAME": database,
            "ARANGO_PASSWORD": password,
        }

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from arango import ArangoClient
from iams.utils.arangodb import Arango

logger = logging.getLogger(__name__)


class ArangoDBMixin(object):
    """
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        hosts = os.environ.get('ARANGO_HOSTS', None)
        database = os.environ.get('ARANGO_DATABASE', None)
        username = os.environ.get('ARANGO_USERNAME', None)
        password = os.environ.get('ARANGO_PASSWORD', None)

        self._arango_utils = Arango()  # TODO
        self._arango_client = self._arango_utils.client

        # TODO
        self._arango = ArangoClient(hosts=hosts).db(database, username=username, password=password, verify=True)

    def _configure(self):
        # TODO add agent to arango-db
        super()._configure()

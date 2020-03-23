#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from arango import ArangoClient

logger = logging.getLogger(__name__)


class ArangoDBMixin(object):
    """
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._arango = ArangoClient(hosts=os.environ.get('ARANGO_HOSTS', None)).db(
            os.environ.get('ARANGO_DATABASE', None),
            username=os.environ.get('ARANGO_USERNAME', None),
            password=os.environ.get('ARANGO_PASSWORD', None),
            verify=True,
        )

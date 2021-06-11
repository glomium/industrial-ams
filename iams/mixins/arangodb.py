#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mixin to add argangodb client to agent
"""

import logging
import os

from abc import ABC
from abc import abstractmethod

from iams.proto.framework_pb2 import Node
# from iams.proto.framework_pb2 import Edge


logger = logging.getLogger(__name__)


try:
    from iams.utils.arangodb import Arango
except ImportError:
    logger.exception("ArangoDB not found")


class ArangoDBMixin(ABC):
    """
    ArangoDB mixin
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        hosts = os.environ.get('ARANGO_HOSTS', None)
        database = os.environ.get('ARANGO_DATABASE', None)
        username = os.environ.get('ARANGO_USERNAME', None)
        password = os.environ.get('ARANGO_PASSWORD', None)

        self._arango_utils = Arango(username=username, password=password, database=database, hosts=hosts)
        self._arango_client = self._arango_utils.db


class TopologyMixin(ArangoDBMixin, ABC):
    """
    Callbacks to manipulate toplogy (replaced by DF)
    """

    def _configure(self):
        super()._configure()
        self.topology_update()

    def topology_get_abilities(self):  # pylint: disable=no-self-use
        """
        get abilities
        """
        return {}

    def topology_get_edges(self):  # pylint: disable=no-self-use
        """
        returns a list of all edges
        """
        return []

    @abstractmethod
    def topology_default_edge(self):
        """
        get default edge
        """

    def topology_get_pools(self):  # pylint: disable=no-self-use
        """
        get pools
        """
        return []

    def topology_update(self):
        """
        returns a list of all edges
        """
        self.iams.update_topology(Node(
            default=self.topology_default_edge(),
            edges=self.topology_get_edges(),
            abilities=self.topology_get_abilities(),
            pools=self.topology_get_pools(),
        ))

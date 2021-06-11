#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

"""
Directory facilitator classes
"""

import logging

from iams.interfaces.df import DirectoryFacilitatorInterface


logger = logging.getLogger(__name__)


class ArangoDF(DirectoryFacilitatorInterface):
    """
    Uses ArangoDB as DF
    """

    def __call__(self):
        """
        Connects the class to argangodb server
        """

    def agents(self, **kwargs):
        """
        Get agents with matching filters
        """

    def register_agent(self, name, **kwargs):
        """
        add agent
        """

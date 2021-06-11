#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

"""
DF interface
"""

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class DirectoryFacilitatorInterface(ABC):
    """
    DF interface
    """
    __hash__ = None

    @abstractmethod
    def __call__(self):
        """
        Initialize DF
        """

    @abstractmethod
    def agents(self, **kwargs):
        """
        Get agents with matching filters
        """

    @abstractmethod
    def register_agent(self, name, **kwargs):
        """
        add agent
        """

#   @abstractmethod
#   def unregister_agent(self, name, **kwargs):
#       """
#       remove agent
#       """

#   @abstractmethod
#   def connections(self, agent, category, **kwargs):
#       """
#       Get agents with matching filters
#       """

#   @abstractmethod
#   def add_connection(self, agent, category, other, **kwargs):
#       """
#       Adds a connection between agents
#       """

#   @abstractmethod
#   def remove_connection(self, agent, category, other, **kwargs):
#       """
#       removes a connection between agents
#       """

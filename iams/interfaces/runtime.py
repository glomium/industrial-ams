#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

"""
runtime interface
"""

import logging

from abc import ABC
from abc import abstractmethod

from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class RuntimeInterface(ABC):
    """
    runtime interface
    """
    __hash__ = None

    def __init__(self) -> None:
        self.plugins = []

    @abstractmethod
    def get_valid_agent_name(self, name):
        """
        returns the validated agent name, or raises an InvalidAgentName
        """

    @abstractmethod
    def get_agent_plugins(self, name):
        """
        get agent plugins
        """

    @abstractmethod
    def get_agent_config(self, name):
        """
        get agent config
        """

    @abstractmethod
    def delete_agent(self, name):
        """
        delete agent
        """

    @abstractmethod
    def delete_agent_secrets(self, name):
        """
        delete agent secrets
        """

    @abstractmethod
    def delete_agent_configs(self, name):
        """
        delete agent configs
        """

    @abstractmethod
    def update_agent(self, request, create=False, update=False):
        """
        update_agent
        """

    @abstractmethod
    def sleep_agent(self, name):
        """
        sleep_agent
        """

    @abstractmethod
    def wake_agent(self, name):
        """
        wake_agent
        """

    def delete_agent_plugins(self, name):
        """
        delete agent plugins
        """
        for plugin, args in self.get_agent_plugins(name):
            plugin.remove(name, args)

    def register_plugin(self, plugin):
        """
        register plugins
        """
        assert isinstance(plugin, Plugin)
        logger.debug('register plugin %s', repr(plugin))
        self.plugins.append(plugin)

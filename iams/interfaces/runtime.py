#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod

from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class RuntimeInterface(ABC):
    """
    """
    __hash__ = None

    def __init__(self) -> None:
        self.plugins = []

    @abstractmethod
    def get_valid_agent_name(self, name):  # pragma: no cover
        """
        returns the validated agent name, or raises an InvalidAgentName
        """
        pass

    @abstractmethod
    def get_agent_plugins(self, name):  # pragma: no cover
        pass

    @abstractmethod
    def get_agent_config(self, name):  # pragma: no cover
        pass

    @abstractmethod
    def delete_agent(self, service):  # pragma: no cover
        pass

    @abstractmethod
    def delete_agent_secrets(self, name):  # pragma: no cover
        pass

    @abstractmethod
    def delete_agent_configs(self, name):  # pragma: no cover
        pass

    @abstractmethod
    def update_agent(self, request, create=False, update=False):  # pragma: no cover
        pass

    @abstractmethod
    def sleep_agent(self, name):  # pragma: no cover
        pass

    @abstractmethod
    def wake_agent(self, name):  # pragma: no cover
        pass

    def delete_agent_plugins(self, name):
        for plugin, args in self.get_agent_plugins(name):
            plugin.remove(name, args)

    def register_plugin(self, plugin):
        assert isinstance(plugin, Plugin)
        logger.debug('register plugin %s', repr(plugin))
        self.plugins.append(plugin)

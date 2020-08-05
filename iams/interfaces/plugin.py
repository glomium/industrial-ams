#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod

logger = logging.getLogger(__name__)


class Plugin(ABC):

    __hash__ = None

    def __init__(self, namespace, simulation):
        self.namespace = namespace
        self.simulation = simulation

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__qualname__, self.namespace)

    def __call__(self, name, image, version, config):
        kwargs = self.get_kwargs(name, image, version, config)

        return (
            self.get_env(**kwargs),
            self.get_labels(**kwargs),
            set(self.get_networks(**kwargs)),
            self.get_configured_secrets(**kwargs),
            self.get_generated_secrets(**kwargs),
        )

    @classmethod
    @abstractmethod
    def label(cls):  # pragma: no cover
        pass

    def remove(self, name, config):
        """
        called when agent is removed
        """
        pass

    def get_kwargs(self, name, image, version, config):
        """
        generate keyword arguements
        """
        return {}

    def get_labels(self, **kwargs):
        """
        set labels for agent
        """
        return {}

    def get_env(self, **kwargs):
        """
        set enviromment variables for agent
        """
        return {}

    def get_networks(self, **kwargs):
        """
        add agent to networks
        """
        return []

    def get_configured_secrets(self, **kwargs):
        """
        add preconfigured secret to agent
        """
        return {}

    def get_generated_secrets(self, **kwargs):
        """
        add automatically generated secret to agent
        """
        return []

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
iams server plugins
"""

import logging

from abc import ABC
from abc import abstractmethod

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """
    iams server plugins
    """

    __hash__ = None

    def __init__(self, namespace, simulation):
        self.namespace = namespace
        self.simulation = simulation

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.namespace})"

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
        """
        returns the label with is matched with the runtime
        """

    def remove(self, name, config):
        """
        called when agent is removed
        """

    def get_kwargs(self, name, image, version, config):  # pylint: disable=unused-argument,no-self-use
        """
        generate keyword arguements
        """
        return {}

    def get_labels(self, **kwargs):  # pylint: disable=unused-argument,no-self-use
        """
        set labels for agent
        """
        return {}

    def get_env(self, **kwargs):  # pylint: disable=unused-argument,no-self-use
        """
        set enviromment variables for agent
        """
        return {}

    def get_networks(self, **kwargs):  # pylint: disable=unused-argument,no-self-use
        """
        add agent to networks
        """
        return []

    def get_configured_secrets(self, **kwargs):  # pylint: disable=unused-argument,no-self-use
        """
        add preconfigured secret to agent
        """
        return {}

    def get_generated_secrets(self, **kwargs):  # pylint: disable=unused-argument,no-self-use
        """
        add automatically generated secret to agent
        """
        return []

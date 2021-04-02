#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

"""
Handles the communication with certificate authorities
"""

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class CertificateAuthorityInterface(ABC):
    """
    Handles the communication with certificate authorities
    """
    __hash__ = None

    @abstractmethod
    def __call__(self):
        """
        Init CA
        """

    @abstractmethod
    def get_root_cert(self):
        """
        Returns the public root certificate from the CA
        """

    @abstractmethod
    def get_ca_secret(self, data, namespace):
        """
        when creating agents this returs the secret containing the CA
        (currently the secret is configured globally - might be subject to change)
        """

    @abstractmethod
    def get_agent_certificate(self, name, hosts=None):
        """
        Get certificate for an agent
        """

    @abstractmethod
    def get_service_certificate(self, name, hosts=None):
        """
        Get certificate for a service
        """

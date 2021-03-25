#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class CertificateAuthorityInterface(ABC):
    """
    """
    __hash__ = None

    @abstractmethod
    def __call__(self):  # pragma: no cover
        pass

    @abstractmethod
    def get_ca_secret(self, data, namespace):  # pragma: no cover
        pass

    @abstractmethod
    def get_agent_certificate(self, name, hosts=None):  # pragma: no cover
        pass

    @abstractmethod
    def get_service_certificate(self, name, hosts=None):  # pragma: no cover
        pass

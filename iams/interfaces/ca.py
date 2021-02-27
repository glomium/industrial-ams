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
    def get_agent_certificate(self, name, image, version):
        pass

    @abstractmethod
    def get_service_certificate(self, name, hosts):
        pass

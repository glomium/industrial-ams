#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class Interface(ABC):

    __hash__ = None

    @abstractmethod
    def __init__(self):
        pass

    def __repr__(self):
        return self.__class__.__qualname__ + f"(host={self.servername}, ns={self.namespace})"

    @property
    @abstractmethod
    def namespace(self):
        pass

    @property
    @abstractmethod
    def namespace_label(self):
        pass

    @property
    @abstractmethod
    def servername(self):
        pass

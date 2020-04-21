#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class Interface(ABC):

    __hash__ = None

    @abstractmethod
    def __init__(self):  # pragma: no cover
        pass

    def __repr__(self):
        return self.__class__.__qualname__ + f"(host={self.servername}, ns={self.namespace})"

    @property
    @abstractmethod
    def namespace(self):  # pragma: no cover
        pass

    @property
    @abstractmethod
    def namespace_label(self):  # pragma: no cover
        pass

    @property
    @abstractmethod
    def servername(self):  # pragma: no cover
        pass

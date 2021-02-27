#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class DirectoryFacilitatorInterface(ABC):
    """
    """
    __hash__ = None

    @abstractmethod
    def __call__(self):  # pragma: no cover
        pass

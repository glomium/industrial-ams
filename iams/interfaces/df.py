#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

"""
DF interface
"""

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class DirectoryFacilitatorInterface(ABC):
    """
    DF interface
    """
    __hash__ = None

    @abstractmethod
    def __call__(self):
        """
        Initialize DF
        """

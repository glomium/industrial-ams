#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Event mixin - usefull for gRPC-only agents
"""

import logging

from abc import ABC
from abc import abstractmethod


logger = logging.getLogger(__name__)


class EventMixin(ABC):
    """
    Usefull for gRPC-only agents
    """

    @abstractmethod
    def loop(self):
        """
        overwrite loop
        """

    def _loop(self):
        logger.debug("Starting control loop")
        while self._loop_event.wait():
            if self._stop_event.is_set():
                break
            self._loop_event.clear()
            logger.debug("Running control loop")
            self.loop()
        logger.debug("Exit control loop")

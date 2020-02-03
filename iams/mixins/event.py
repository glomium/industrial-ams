#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging


logger = logging.getLogger(__name__)


class EventMixin(object):
    """
    Usefull for gRPC-only agents
    """

    def loop(self):
        raise NotImplementedError("%s.loop is not implemented", self.__class__.__qualname__)

    def _loop(self):
        logger.debug("Starting control loop")
        while self._loop_event.wait():
            if self._stop_event.is_set():
                break
            self._loop_event.clear()
            logger.debug("Running control loop")
            self.loop()
        logger.debug("Exit control loop")

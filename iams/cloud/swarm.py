#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from .interface import Interface


logger = logging.getLogger(__name__)


class Swarm(Interface):

    def __init__(self, labels):
        self._namespace = labels["com.docker.stack.namespace"]
        self._servername = labels["com.docker.swarm.service.name"]
        self._servername = "tasks." + self._servername[len(self._namespace) + 1:]
        logger.info("Cloud: %r", self)

    @property
    def namespace(self):
        return self._namespace

    @property
    def namespace_label(self):
        return "com.docker.stack.namespace"

    @property
    def servername(self):
        return self._servername

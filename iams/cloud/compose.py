#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from .interface import Interface


logger = logging.getLogger(__name__)


class Compose(Interface):

    def __init__(self, labels):
        self._namespace = labels["com.docker.compose.project"]
        self._servername = labels["com.docker.compose.service"]
        logger.info("Cloud: %r", self)

    @property
    def namespace(self):
        return self._namespace

    @property
    def namespace_label(self):
        return "com.docker.compose.project"

    @property
    def servername(self):
        return self._servername

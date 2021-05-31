#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add InfluxDB functionality to agents
"""

import logging

logger = logging.getLogger(__name__)


class InfluxMixin:
    """
    Mixin to add InfluxDB functionality to agents
    """

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     credentials = None
    #     self._grpc = GRPCCoroutine(credentials)

    # def _pre_setup(self):
    #     super()._pre_setup()
    #     self.task_manager.register(self._grpc)

    def influxdb_write(self, data, time=None):
        """
        write data to influxdb
        """

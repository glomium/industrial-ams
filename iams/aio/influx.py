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
    #     self.aio_manager.register(self._grpc)

    def influxdb_write(self, data, time=None):
        """
        write data to influxdb
        """


_ = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
influxdb mixin
"""

import datetime
import logging
import os
import socket

logger = logging.getLogger(__name__)

HOST = os.environ.get('INFLUXDB_HOST', None)
DATABASE = os.environ.get('INFLUXDB_DATABASE', None)


if HOST is None or DATABASE is None:
    logger.debug("InfluxDB hostname or database not specified")
    INFLUXDB = False

try:
    from influxdb import InfluxDBClient
    INFLUXDB = True
except ImportError:
    logger.info("Could not import influxdb library")
    INFLUXDB = False


class InfluxDBMixin:
    """
    influxdb mixin
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if INFLUXDB:
            self._influxdb = InfluxDBClient(host=HOST, database=DATABASE, timeout=0.5)
            logger.info("Influxdb initialized with host %s", HOST)

    def influxdb_write(self, data, time=None):
        """
        sends data (list of dictionaries) to influx-database
        """

        if not INFLUXDB:
            return None

        if time is not None:
            now = datetime.datetime.utcnow()
            for i, entry in enumerate(data):
                if "time" not in entry:
                    data[i]["time"] = now

        try:
            self._executor.submit(self._influxdb_write, data)
        except RuntimeError:
            pass

        return None

    def _influxdb_write(self, data):
        try:
            self._influxdb.write_points(data, time_precision="ms")
        except socket.timeout:
            pass
'''

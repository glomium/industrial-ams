#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import datetime
import logging
import os
import socket

logger = logging.getLogger(__name__)

try:
    from influxdb import InfluxDBClient
    INFLUXDB = True
except ImportError:
    INFLUXDB = False

HOST = os.environ.get('INFLUXDB_HOST', None)
DATABASE = os.environ.get('INFLUXDB_DATABASE', "modelfactory")

if HOST is None:
    INFLUXDB = False


class InfluxDBMixin(object):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if INFLUXDB:
            self._influxdb = InfluxDBClient(host=HOST, database=DATABASE, timeout=0.5)
            logger.info("Infludb initialized with host %s", HOST)

    def influxdb_send(self, data, time=None):
        if not INFLUXDB:
            return None

        if time is None:
            now = datetime.datetime.now()
            for i in range(len(data)):
                if "time" not in data[i]:
                    data[i]["time"] = now

        try:
            self._executor.submit(self._influxdb_write, data)
        except RuntimeError:
            pass

    def _influxdb_write(self, data):
        try:
            self._influxdb.write_points(data, time_precision="ms")
        except socket.timeout:
            pass

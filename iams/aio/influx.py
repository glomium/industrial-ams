#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add InfluxDB functionality to agents
"""

from datetime import datetime
from functools import partial
import logging
import os

from iams.aio.interfaces import ThreadCoroutine


logger = logging.getLogger(__name__)


try:
    from influxdb_client import InfluxDBClient
    from influxdb_client import Point
    from influxdb_client.client.write_api import PointSettings
    from influxdb_client.client.write_api import WriteOptions
    from influxdb_client.client.write_api import WriteType
    ENABLED = True
except ImportError:
    logger.info("Could not import influxdb_client library")
    ENABLED = False

BUCKET = os.environ.get('INFLUX_BUCKET', None)
HOST = os.environ.get('INFLUX_HOST', None)
ORG = os.environ.get('INFLUX_ORG', None)
TOKEN = os.environ.get('INFLUX_TOKEN', None)

if BUCKET is None:
    logger.info("INFLUX_BUCKET is not specified")
    ENABLED = False
elif HOST is None:
    logger.info("INFLUX_HOST is not specified")
    ENABLED = False
elif ORG is None:
    logger.info("INFLUX_ORG is not specified")
    ENABLED = False
elif TOKEN is None:
    logger.info("INFLUX_TOKEN is not specified")
    ENABLED = False


class InfluxCoroutine(ThreadCoroutine):  # pylint: disable=too-many-instance-attributes
    """
    InfluxDB Coroutine
    """

    def __init__(self, url, bucket, token, org):
        logger.debug("Initialize Influx coroutine")
        super().__init__()
        self.bucket = bucket
        self.client = None
        self.org = org
        self.token = token
        self.url = url
        self.write_api = None

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        self.client = await self._loop.run_in_executor(self._executor, partial(
            InfluxDBClient,
            org=self.org,
            token=self.token,
            url=self.url,
        ))
        self.write_api = await self._loop.run_in_executor(self._executor, partial(
            self.client.write_api,
            point_settings=PointSettings(),
            write_options=WriteOptions(
                flush_interval=5000,
                write_type=WriteType.asynchronous,
            ),
        ))

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if await super().stop():
            await self._loop.run_in_executor(self._executor, self.write_api.close)
            await self._loop.run_in_executor(self._executor, self.client.close)

    async def write(self, data, precision):
        """
        stop method is called after the coroutine was canceled
        """
        await self._loop.run_in_executor(self._executor, partial(
            self.write_api.write,
            bucket=self.bucket,
            record=[Point.from_dict(value) for value in data],
            write_precision=precision,
        ))


class InfluxMixin:
    """
    Mixin to add InfluxDB functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if ENABLED:
            self._influx = InfluxCoroutine(HOST, BUCKET, TOKEN, ORG)
        else:
            logger.debug(
                "Influx is disabled, HOST=%s BUCKET=%s TOKEN=%s ORG=%s",
                HOST,
                BUCKET,
                TOKEN,
                ORG,
            )

    def _setup(self):
        super()._setup()
        if ENABLED:
            self.aio_manager.register(self._influx)

    async def influxdb_write(self, data, time=None, precision="ms"):
        """
        write data to influxdb
        """
        if ENABLED:
            if time is None:
                time = datetime.utcnow()

            for i, entry in enumerate(data):
                if "time" not in entry:
                    data[i]["time"] = time

            await self._influx.write(data, precision)

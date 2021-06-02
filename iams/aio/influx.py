#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add InfluxDB functionality to agents
"""

from datetime import datetime
from functools import partial
import asyncio
import logging
import os


from iams.aio.interfaces import Coroutine


logger = logging.getLogger(__name__)


try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import ASYNCHRONOUS
    ENABLED = True
except ImportError:
    logger.info("Could not import influxdb_client library")
    ENABLED = False


CLOUD = os.environ.get('INFLUXDB_CLOUD', None)
BUCKET = os.environ.get('INFLUXDB_BUCKET', None)
TOKEN = os.environ.get('INFLUXDB_TOKEN', "my-token")
ORG = os.environ.get('INFLUXDB_ORG', None)

if CLOUD is None:
    logger.debug("INFLUXDB_CLOUD is not specified")
    ENABLED = False
elif BUCKET is None:
    logger.debug("INFLUXDB_BUCKET is not specified")
    ENABLED = False


class InfluxCoroutine(Coroutine):  # pylint: disable=too-many-instance-attributes
    """
    InfluxDB Coroutine
    """

    def __init__(self, url, bucket, token=None, org=None):
        self._executor = None
        self._stop = None
        self.bucket = bucket
        self.client = None
        self.org = org
        self.token = token
        self.url = url
        self.write_api = None

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        self.client = await self._loop.run_in_executor(executor, partial(
            InfluxDBClient,
            url=self.url,
            token=self.token,
        ))
        self.write_api = await self._loop.run_in_executor(executor, partial(
            self.client.write_api,
            token=self.token,
            write_options=ASYNCHRONOUS,
            flush_interval=5000,
        ))
        self._stop = self._loop.create_future()

    async def loop(self):
        """
        loop method contains the business-code
        """
        await asyncio.wait_for(self._stop, timeout=None)

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if not self._stop.done():
            self._stop.set_result(None)
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
            self._influx = InfluxCoroutine(CLOUD, BUCKET, token=TOKEN, org=ORG)

    def _pre_setup(self):
        super()._pre_setup()
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

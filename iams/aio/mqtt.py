#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add MQTT functionality to agents
"""

from functools import partial
import asyncio
import logging
import os

from iams.aio.interfaces import Coroutine

logger = logging.getLogger(__name__)

HOST = os.environ.get('MQTT_HOST', None)
PORT = int(os.environ.get('MQTT_PORT', 1883))
TOPIC = os.environ.get('MQTT_TOPIC', None)


try:
    import paho.mqtt.client as mqttclient
except ImportError:  # pragma: no branch
    logger.exception("Could not import mqtt library")
    MQTT = False
else:
    LOG_MAP = {
        mqttclient.MQTT_LOG_DEBUG: logging.DEBUG,
        mqttclient.MQTT_LOG_NOTICE: logging.INFO,
        mqttclient.MQTT_LOG_INFO: logging.INFO,
        mqttclient.MQTT_LOG_WARNING: logging.WARNING,
        mqttclient.MQTT_LOG_ERR: logging.ERROR,
    }
    MQTT = True


if HOST is None:
    logger.debug("mqtt hostname is not specified")
    MQTT = False


def on_log(client, userdata, level, buf):  # pylint: disable=unused-argument # pragma: no cover
    """
    redirect logs to python logging system
    """
    logger.log(LOG_MAP[level], buf)


class MQTTCoroutine(Coroutine):
    """
    MQTT Coroutine
    """

    def __init__(self, parent):
        self._client = mqttclient.Client()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_log = on_log
        self._client.on_message = self._on_message
        self._connected = False
        self._executor = None
        self._loop = parent.task_manager.loop
        self._parent = parent
        self._stop = self._loop.create_future()

    def _on_connect(self, client, userdata, flags, return_code):
        logger.info("Connected to MQTT-Broker with result code %s", return_code)
        self._connected = True
        self._loop.create_task(self._parent.mqtt_on_connect(client, userdata, flags, return_code))

    def _on_disconnect(self, client, userdata, return_code):
        logger.info("Disconnected from MQTT-Broker with result code %s", return_code)
        self._connected = False
        self._loop.create_task(self._parent.mqtt_on_disconnect(client, userdata, return_code))

    def _on_message(self, client, userdata, message):
        logger.debug("Got message: %s", message)
        self._loop.create_task(self._parent.mqtt_on_message(client, userdata, message))

    async def publish(self, payload, topic, qos, retain):
        """
        sends data to MQTT
        """
        await self._loop.run_in_executor(self._executor, partial(
            self._client.publish,
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain,
        ))

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        while True:
            logger.debug("Try to establish MQTT connection with %s:%s", HOST, PORT)
            try:
                await self._loop.run_in_executor(
                    executor, self._client.connect,
                    HOST, PORT,
                )
                break
            except OSError:
                pass
            await asyncio.sleep(1)

        logger.info("MQTT initialized with %s:%s", HOST, PORT)
        await self._loop.run_in_executor(
            executor, self._client.loop_start,
        )
        self._executor = executor

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
            await self._loop.run_in_executor(self._executor, partial(
                self._client.loop_stop,
                force=True,
            ))


class MQTTMixin:
    """
    Mixin to add MQTT functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if MQTT:
            self._mqtt = MQTTCoroutine(self)

    def _pre_setup(self):
        super()._pre_setup()
        if MQTT:
            self.task_manager.register(self._mqtt)

    async def mqtt_on_connect(self, client, userdata, flags, return_code):
        """
        callback for mqtt on_connect information
        """

    async def mqtt_on_disconnect(self, client, userdata, return_code):
        """
        callback for mqtt on_disconnect information
        """

    async def mqtt_on_message(self, client, userdata, message):
        """
        callback for mqtt messages
        """

    async def mqtt_publish(self, payload=None, topic=TOPIC, qos=0, retain=False):
        """
        sends data to MQTT
        """
        if not MQTT:
            return False

        try:
            await self._mqtt.publish(topic=topic, payload=payload, qos=qos, retain=retain)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error publishing MQTT-message")
            return False
        return True

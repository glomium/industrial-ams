#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mixin to add MQTT functionality to agents
"""

import logging
import os

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


class MQTTMixin:
    """
    Mixin to add MQTT functionality to agents
    """

    def _pre_setup(self):
        super()._pre_setup()
        if MQTT:
            self._mqtt = mqttclient.Client()
            self._mqtt.on_connect = self.mqtt_on_connect
            self._mqtt.on_message = self.mqtt_on_message
            self._mqtt.on_log = on_log
            while True:
                try:
                    self._mqtt.connect(HOST, PORT)
                    break
                except OSError:
                    pass
            self._mqtt.loop_start()
            logger.info("MQTT initialized with %s:%s", HOST, PORT)

    def _teardown(self):
        super()._teardown()
        if MQTT:
            self._mqtt.loop_stop(force=True)

    def mqtt_on_connect(self, client, userdata, flags, rc):  # pylint: disable=unused-argument,no-self-use,invalid-name
        """
        callback for mqtt on_connect information
        """
        logger.info("Connected to MQTT-Broker with result code %s", rc)

    def mqtt_on_message(self, client, userdata, message):  # pylint: disable=unused-argument,no-self-use
        """
        callback for mqtt messages
        """
        logger.debug("Got message %s", message)

    def mqtt_publish(self, topic=TOPIC, payload=None, qos=0, retain=False):
        """
        sends data (list of dictionaries) to MQTT
        """
        if not MQTT:
            return False

        try:
            self._mqtt.publish(topic, payload=payload, qos=qos, retain=retain)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error publishing MQTT-message")

        return True

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

logger = logging.getLogger(__name__)

HOST = os.environ.get('MQTT_HOST', None)
PORT = int(os.environ.get('MQTT_HOST', 1883))
TOPIC = os.environ.get('MQTT_TOPIC', None)


if HOST is None:
    logger.debug("mqtt hostname is not specified")
    MQTT = False

try:
    import paho.mqtt.client as mqttclient
    MQTT = True
    LOG_MAP = {
        mqttclient.MQTT_LOG_DEBUG: logging.DEBUG,
        mqttclient.MQTT_LOG_NOTICE: logging.INFO,
        mqttclient.MQTT_LOG_INFO: logging.INFO,
        mqttclient.MQTT_LOG_WARNING: logging.WARNING,
        mqttclient.MQTT_LOG_ERR: logging.ERROR,
    }
except ImportError:
    logger.info("Could not import mqtt library")
    MQTT = False


def on_log(client, userdata, level, buf):  # pragma: no cover
    """
    redirect logs to python logging system
    """
    logger.log(LOG_MAP[level], buf)


class MQTTMixin(object):
    """
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if MQTT:
            self._mqtt = mqttclient.Client()
            self._mqtt.on_connect = self.on_connect
            self._mqtt.on_message = self.on_message
            self._mqtt.on_log = on_log

    def _pre_setup(self):
        super()._pre_setup()
        if MQTT:
            while True:
                try:
                    self._mqtt.connect(HOST, PORT)
                    break
                except OSError:
                    pass
            self._mqtt.loop_start()
            logger.info(f"MQTT initialized with {HOST}:{PORT}")

    def _teardown(self):
        super()._teardown()
        if MQTT:
            self._mqtt.loop_stop(force=True)

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logger.info("Connected with result code %s", rc)

    def mqtt_on_message(self, client, userdata, message):
        logger.debug("Got message %s", message)

    def mqtt_publish(self, topic=TOPIC, payload=None, qos=0, retain=False):
        """
        sends data (list of dictionaries) to MQTT
        """
        if not MQTT or topic:
            return False
        self._mqtt.publish(topic, payload=payload, qos=qos, retain=retain)
        return True

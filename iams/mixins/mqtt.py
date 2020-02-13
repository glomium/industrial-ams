#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

import paho.mqtt.client as mqttclient


logger = logging.getLogger(__name__)

LOG_MAP = {
    mqttclient.MQTT_LOG_DEBUG: logging.DEBUG,
    mqttclient.MQTT_LOG_NOTICE: logging.INFO,
    mqttclient.MQTT_LOG_INFO: logging.INFO,
    mqttclient.MQTT_LOG_WARNING: logging.WARNING,
    mqttclient.MQTT_LOG_ERR: logging.ERROR,
}


def on_message(client, userdata, message):
    logger.debug("Got message %s", message)


def on_log(client, userdata, level, buf):  # pragma: no cover
    """
    redirect logs to python logging system
    """
    logger.log(LOG_MAP[level], buf)


def on_connect(client, userdata, flags, rc):  # pragma: no cover
    logger.info("Connected with result code %s", rc)

    logger.debug("Subscribe to $SYS/broker/load/connections/1min")
    client.subscribe("$SYS/broker/load/connections/1min")

    logger.debug("Subscribe to $SYS/broker/load/sockets/1min")
    client.subscribe("$SYS/broker/load/sockets/1min")

    logger.debug("Subscribe to $SYS/broker/load/messages/+/1min")
    client.subscribe("$SYS/broker/load/messages/+/1min")

    logger.debug("Subscribe to $SYS/broker/load/bytes/+/1min")
    client.subscribe("$SYS/broker/load/bytes/+/1min")

    logger.debug("Subscribe to data/+")
    client.subscribe("data/+")
    logger.debug("Subscribe to data/+/+")
    client.subscribe("data/+/+")
    logger.debug("Subscribe to data/+/+/+")
    client.subscribe("data/+/+/+")


if __name__ == "__main__":
    logger.info("Starting mqtt listener")
    client = mqttclient.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_log = on_log
    try:
        client.connect(
            "tasks.mqtt",
            1883,
        )
    except OSError:
        raise SystemExit("Could not connect to MQTT-Broker")
    client.loop_forever(retry_first_connection=True)

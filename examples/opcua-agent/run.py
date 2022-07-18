#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import asyncio
import logging

from asyncua.ua import VariantType

from iams.agent import Agent
from iams.aio.influx import InfluxMixin
from iams.aio.opcua import OPCUAMixin


logger = logging.getLogger(__name__)


class Conveyor(OPCUAMixin, InfluxMixin, Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensor1_node = None
        self.sensor2_node = None
        self.sensor1_value = None
        self.sensor2_value = None

    def opcua_kwargs(self):
        kwargs = super().opcua_kwargs()
        kwargs.update({
            # "port": 14048,  # use this to change the port
            "session_timeout": 15,
        })
        return kwargs

    async def opcua_keepalive(self):
        """
        """
        try:
            await self.sensor1_node.get_value()
        except Exception:  # pylint: disable=broad-except
            return False

    async def opcua_start(self):
        """
        """
        self.sensor1_node = await self.opcua_node(name="sensor1", path=["3:ServerInterfaces", "4:Test", "4:Sensor1"])
        self.sensor2_node = await self.opcua_node(name="sensor2", path=["3:ServerInterfaces", "4:Test", "4:Sensor2"])

        await self.opcua_subscribe([self.sensor1_node, self.sensor2_node], 100)

    async def opcua_datachange(self, node, val, data):
        """
        """

        if node == self.sensor1_node:
            previous = self.sensor1_value
            self.sensor1_value = val
        elif node == self.sensor2_node:
            previous = self.sensor2_value
            self.sensor2_value = val
        logger.debug("%s changed from '%s' to '%s'", node, previous, val)

    async def opcua_datachanges(self, changes):
        """
        """
        tags = {
            "address": self.iams.address,
        }
        fields = {
            "sensor1": self.sensor1_value,
            "sensor2": self.sensor2_value,
        }

        await self.influxdb_write([{
            "measurement": "my_agent",
            "tags": tags,
            "fields": fields,
        }])


if __name__ == "__main__":

    from logging.config import dictConfig
    from iams.helper import get_logging_config

    dictConfig(get_logging_config({
        "asyncua": {"level": "ERROR"},
        "iams": {"level": "DEBUG"},
    }, logging.DEBUG))

    run = MyAgent()
    run()

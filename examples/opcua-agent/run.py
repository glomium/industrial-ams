#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from iams.agent import Agent
from iams.aio.influx import InfluxMixin
from iams.aio.opcua import OPCUAMixin


logger = logging.getLogger(__name__)


class MyAgent(OPCUAMixin, InfluxMixin, Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # store node an values on instance
        self.sensor1_node = None
        self.sensor1_value = None
        self.sensor2_node = None
        self.sensor2_value = None
        self.server_time_node = None
        self.server_time_value = None

    def opcua_kwargs(self):
        """
        Configure OPC-UA client
        """
        kwargs = super().opcua_kwargs()
        kwargs.update({
            # "port": 14048,  # use this to change the port
            "session_timeout": 15,  # the session should close after 15 seconds
        })
        return kwargs

    async def opcua_start(self):
        """
        callback after opc-ua starts
        """
        self.sensor1_node = await self.opcua_node(name="sensor1", path=["3:ServerInterfaces", "4:Test", "4:Sensor1"])
        self.sensor2_node = await self.opcua_node(name="sensor2", path=["3:ServerInterfaces", "4:Test", "4:Sensor2"])
        self.server_time_node = await self.opcua_node(name="server_time", path="i=2258")

        # create subscription (update every 100 ms)
        await self.opcua_subscribe([self.server_time, self.sensor1_node, self.sensor2_node], 100)

    async def opcua_datachange(self, node, val, data):
        """
        callback for every node that has a subscription, when it's value changes
        identifies a node, stores its value and writes a log message containing the old and new values
        """
        if node == self.server_time_node:
            self.server_time_value = val
        elif node == self.sensor1_node:
            previous = self.sensor1_value
            self.sensor1_value = val
        elif node == self.sensor2_node:
            previous = self.sensor2_value
            self.sensor2_value = val
        logger.info("%s changed from '%s' to '%s'", node, previous, val)

    async def opcua_datachanges(self, changes):
        """
        called with all datachanges from one opc-ua update package

        used to send data to influxdb
        """

        tags = {
            "address": self.iams.address,  # used the address stored within the agent
        }
        fields = {
            "sensor1": self.sensor1_value,
            "sensor2": self.sensor2_value,
        }

        # send data to influxdb
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

#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging

from opcua.client.client import Client
from opcua.common.subscription import SubHandler
from opcua.ua.uatypes import DataValue
from opcua.ua.uatypes import Variant

from .event import EventMixin


logger = logging.getLogger(__name__)


class Handler(SubHandler):

    def __init__(self, parent):
        self.parent = parent

    def datachange_notification(self, node, val, data):
        """
        """
        logger.debug("New data change event %s %s", node, val)
        self.parent.opcua_datachange(node, val, data)
        self.parent._loop_event.set()

    def event_notification(self, event):
        """
        """
        logger.debug("New event %s", event)
        self.parent.opcua_event(event)
        self.parent._loop_event.set()

    def status_change_notification(self, status):
        """
        called for every status change notification from server
        """
        logger.debug("Status changed to %s", status)
        self.parent.opcua_status_change(status)
        # self.parent._loop_event.set()


class OPCUAMixin(EventMixin):
    OPCUA_PORT = 4840
    OPCUA_TIMEOUT = 15
    OPCUA_EVENT_SUBSCRIPTION = None

    def __init__(self, *args, **kwargs) -> None:
        assert self.OPCUA_PORT is not None, "OPCUA_PORT needs to be set on %s" % self.__class__.__qualname__
        super().__init__(*args, **kwargs)

        self.opcua_client = None
        self.opcua_handles = {}
        self.opcua_objects = None
        self.opcua_subscriptions = {}

    def _pre_setup(self):
        super()._pre_setup()
        assert self._iams.address is not None, 'Must define IAMS_ADDRESS in environment'

        address = "opc.tcp://%s:%s/" % (self._iams.address, self._iams.port or self.OPCUA_PORT)
        logger.debug("Creating opcua-client %s", address)
        self.opua_client = Client("opc.tcp://%s/" % address, timeout=10)

        wait = 0
        while not self._stop_event.is_set():
            try:
                self.opcua_client.connect()
                break
            except ConnectionRefusedError:
                if wait < 60:
                    wait += 1
                logger.info('Connection to %s refused (retry in %ss)', address, wait)
                self._stop_event.wait(wait)
        logger.debug("OPCUA connected to %s:%s", address)

        self.opcua_client.load_type_definitions()
        self.opcua_objects = self.opcua_client.get_objects_node()

        if self.OPCUA_EVENT_SUBSCRIPTION:
            subscription = self.opcua_client.create_subscription(self.OPCUA_EVENT_SUBSCRIPTION, SubHandler(self))
            subscription.subscribe_events()
            self.opcua_subscriptions[self.OPCUA_EVENT_SUBSCRIPTION] = subscription

    def opcua_datachange(self, node, val, data):
        """
        """
        pass

    def opcua_event(self, event):
        """
        """
        pass

    def opcua_status_change(self, status):
        """
        """
        pass

    def opcua_write(self, node, value, datatype):
        self.opcua_write_many([node, value, datatype])

    def opcua_write_many(self, data):
        """
        data is a list or tuple of node, value and datatype
        """
        nodes = []
        values = []
        for node, value, datatype in data:
            nodes.append(node)
            values.append(DataValue(Variant(value, datatype)))
        self.opcua_client.set_values(nodes, values)

    def opcua_subscribe(self, node, interval):
        """
        """
        assert node not in self.opcua_handles

        try:
            subscription = self.opcua_handlers[interval]
        except KeyError:
            subscription = self.opcua_client.create_subscription(interval, SubHandler(self))
            self.opcua_subscriptions[interval] = subscription

        handle = subscription.subscribe_data_change(node)
        self.opcua_handles[node] = (subscription, handle)

    def opcua_unsubscribe(self, node):
        """
        """
        try:
            subscription, handle = self.opcua_handles[node]
        except KeyError:
            return None
        subscription.unsubscribe(handle)

    def _teardown(self):
        super()._teardown()
        logger.debug("Closing OPCUA")
        try:
            self.opcua_client.disconnect()
        except (TimeoutError, AttributeError):
            pass

    def _loop(self):
        if not self.client.uaclient._uasocket._thread.isAlive():
            raise NotImplementedError
        super()._loop()

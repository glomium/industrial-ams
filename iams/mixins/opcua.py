#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
opc ua mixin for agents
"""

import logging

from types import MethodType

from iams.mixins.event import EventMixin


logger = logging.getLogger(__name__)


try:
    from opcua.client.client import Client
    from opcua.common.subscription import DataChangeNotif
    from opcua.common.subscription import SubHandler
    from opcua.ua.uatypes import DataValue
    from opcua.ua.uatypes import Variant
except ImportError:  # pragma: no branch
    logger.exception("Could not import opcua library")
    OPCUA = False
else:
    OPCUA = True


def monkeypatch_call_datachange(self, datachange):
    """
    Monkeypatching to have one signal, when a new packet with datachanges arrives.
    """
    # pylint: disable=protected-access
    changes = []
    for item in datachange.MonitoredItems:
        with self._lock:
            if item.ClientHandle not in self._monitoreditems_map:
                self.logger.warning("Received a notification for unknown handle: %s", item.ClientHandle)
                self.has_unknown_handlers = True
                continue
            data = self._monitoreditems_map[item.ClientHandle]
        event_data = DataChangeNotif(data, item)
        changes.append((data.node, item.Value.Value.Value, event_data))
    self._handler.datachange_notifications(changes)


class Handler(SubHandler):
    """
    Subscription Handler. To receive events from server for a subscription
    data_change and event methods are called directly from receiving thread.
    Do not do expensive, slow or network operation there. Create another
    thread if you need to do such a thing
    """

    def __init__(self, parent):
        self.parent = parent

    def datachange_notifications(self, notifications):
        """
        packet datachange notifications
        """
        response = False
        for node, val, data in notifications:
            result = self.datachange_notification(node, val, data)
            if not response and result in [None, True]:
                response = True

        if self.parent.opcua_datachanges(response):
            self.parent._loop_event.set()  # pylint: disable=protected-access

    def datachange_notification(self, node, val, data):
        """
        single datachange notification
        """
        logger.debug("New data change event %s %s", node, val)
        return self.parent.opcua_datachange(node, val, data)

    def event_notification(self, event):
        """
        opcua event notifications
        """
        logger.debug("New event %s", event)
        response = self.parent.opcua_event(event)
        if response is None or response is True:
            self.parent._loop_event.set()  # pylint: disable=protected-access

    def status_change_notification(self, status):
        """
        called for every status change notification from server
        """
        logger.debug("Status changed to %s", status)
        response = self.parent.opcua_status_change(status)
        if response is True:
            self.parent._loop_event.set()  # pylint: disable=protected-access


class OPCUAMixin(EventMixin):  # pylint: disable=abstract-method
    """
    opc ua mixin for agents
    """
    OPCUA_PORT = 4840
    OPCUA_TIMEOUT = 15
    OPCUA_HEARTBEAT = 12.5
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
        assert self.iams.address is not None, 'Must define IAMS_ADDRESS in environment'

        if OPCUA:
            address = "opc.tcp://%s:%s/" % (self.iams.address, self.iams.port or self.OPCUA_PORT)
            logger.debug("Creating opcua-client %s", address)
            self.opcua_client = Client(address, timeout=10)

            wait = 0
            while not self._stop_event.is_set():
                try:
                    self.opcua_client.connect()
                    break
                except (ConnectionRefusedError, OSError):
                    if wait < 60:
                        wait += 1
                    logger.info('Connection to %s refused (retry in %ss)', address, wait)
                    self._stop_event.wait(wait)
            logger.debug("OPCUA connected to %s", address)

            self.opcua_client.load_type_definitions()
            self.opcua_objects = self.opcua_client.get_objects_node()

            if self.OPCUA_EVENT_SUBSCRIPTION:
                subscription = self.opcua_client.create_subscription(self.OPCUA_EVENT_SUBSCRIPTION, Handler(self))
                subscription.subscribe_events()
                self.opcua_subscriptions[self.OPCUA_EVENT_SUBSCRIPTION] = subscription

            if self.OPCUA_HEARTBEAT:
                self._executor.submit(self._opcua_heartbeat)

    def _opcua_heartbeat(self):
        while not self._stop_event.is_set():
            try:
                self.opcua_client.get_values([self.opcua_client.get_objects_node()])
            except Exception:  # pylint: disable=broad-except
                self.stop()
                break
            self._stop_event.wait(self.OPCUA_HEARTBEAT)

    def opcua_datachanges(self, run_loop):  # pylint: disable=no-self-use
        """
        Datachanges callback (one per packet)
        """
        return run_loop

    def opcua_datachange(self, node, val, data):
        """
        Datachange callback (one per subscribed variable)
        """

    def opcua_event(self, event):
        """
        Event callback
        """

    def opcua_status_change(self, status):
        """
        Status-change callback
        """

    def opcua_write(self, node, value, datatype):
        """
        write value to node on opcua-server
        """
        self.opcua_write_many([node, value, datatype])

    def opcua_write_many(self, data):
        """
        data is a list or tuple of node, value and datatype
        """
        if not OPCUA:
            return None
        nodes = []
        values = []
        for node, value, datatype in data:
            nodes.append(node)
            values.append(DataValue(Variant(value, datatype)))
        self.opcua_client.set_values(nodes, values)
        return None

    def opcua_subscribe(self, nodes, interval):
        """
        unsubscribe to topic
        """
        if not OPCUA:
            return None
        try:
            subscription = self.opcua_subscriptions[interval]
        except KeyError:
            # pylint: disable=protected-access
            subscription = self.opcua_client.create_subscription(interval, Handler(self))
            subscription._call_datachange = MethodType(monkeypatch_call_datachange, subscription)
            self.opcua_subscriptions[interval] = subscription

        handle = subscription.subscribe_data_change(nodes)
        try:
            for node in nodes:
                self.opcua_handles[node] = (subscription, handle)
        except TypeError:
            self.opcua_handles[nodes] = (subscription, handle)
        return None

    def opcua_unsubscribe(self, node):
        """
        unsubscribe from topic
        """
        if not OPCUA:
            return None
        try:
            subscription, handle = self.opcua_handles[node]
        except KeyError:
            return None
        subscription.unsubscribe(handle)
        return None

    def _teardown(self):
        super()._teardown()
        logger.debug("Closing OPCUA")
        if OPCUA:
            try:
                self.opcua_client.disconnect()
            except (TimeoutError, AttributeError):
                pass

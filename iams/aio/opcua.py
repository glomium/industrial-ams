#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
opc ua mixin for agents
"""

import asyncio
import logging
import socket
from time import time
from types import MethodType

from iams.aio.interfaces import Coroutine

logger = logging.getLogger(__name__)

try:
    from asyncua import Client
    from asyncua.ua.status_codes import StatusCodes
    from asyncua.ua.status_codes import get_name_and_doc
    from asyncua.ua.uatypes import DataValue
    from asyncua.ua.uatypes import Variant
    from asyncua.common.subscription import DataChangeNotif
except ImportError:  # pragma: no branch
    logger.exception("Could not import opcua library")
    OPCUA = False
else:
    OPCUA = True


async def monkeypatch_call_datachange(self, datachange):
    """
    Monkeypatching to have one signal, when a new packet with datachanges arrives.
    """
    # pylint: disable=protected-access
    # see https://github.com/FreeOpcUa/opcua-asyncio/blob/7d7841bfb7b4e351797b8a5cebdfa68a6418e406/asyncua/common/subscription.py#L126  # noqa: E501
    changes = {}
    for item in datachange.MonitoredItems:
        if item.ClientHandle not in self._monitored_items:
            self.logger.warning("Received a notification for unknown handle: %s", item.ClientHandle)
            continue
        data = self._monitored_items[item.ClientHandle]

        if hasattr(self._handler, "datachange_notification"):
            event_data = DataChangeNotif(data, item)
            try:
                if asyncio.iscoroutinefunction(self._handler.datachange_notification):
                    result = await self._handler.datachange_notification(data.node, item.Value.Value.Value, event_data)
                else:
                    result = self._handler.datachange_notification(data.node, item.Value.Value.Value, event_data)
                changes[data.node] = (result, item.Value.Value.Value)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Exception calling data change handler")
        else:
            logger.error("DataChange subscription created but handler has no datachange_notification method")

    if hasattr(self._handler, "datachange_notifications"):
        try:
            if asyncio.iscoroutinefunction(self._handler.datachange_notifications):
                await self._handler.datachange_notifications(changes)
            else:
                self._handler.datachange_notifications(changes)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Exception calling data changes handler")


class Handler:
    """
    The SubscriptionHandler is used to handle the data that is received for the subscription.
    """

    def __init__(self, parent, coro):
        self.coro = coro
        self.parent = parent

    async def datachange_notification(self, node, val, data):
        """
        Callback for asyncua Subscription.
        """
        logger.debug("%s changed it's value to %s", node, val)
        try:
            return await self.parent.opcua_datachange(node, val, data)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error evaluating datachange of %s with value=%s", node, val)

    async def datachange_notifications(self, changes):
        """
        packet datachange notifications
        """
        try:
            await self.parent.opcua_datachanges(changes)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error evaluating datachanges")

    async def status_change_notification(self, status):  # pylint: disable=no-self-use
        """
        status change notification
        """
        try:
            name, doc = get_name_and_doc(status)
            logger.info("OPC-UA connection status changed to %s (%s)", name, status)
            await self.parent.opcua_statuschange(status, name, doc)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error evaluating statuschange with status=%s, name=%s, doc=%s", status, name, doc)


class OPCUACoroutine(Coroutine):  # pylint: disable=too-many-instance-attributes
    """
    OPCUA Coroutine
    """

    def __init__(self, parent, host, port=4840, session_timeout=5, request_timeout=0.5):  # pylint: disable=too-many-arguments  # noqa: E501
        logger.debug("Initialize OPCUA coroutine")

        self._address = f"opc.tcp://{host}:{port}/"
        self._client = None
        self._names = {}  # cached names (node object to string)
        self._nodes = {}  # cached nodes (string to node object)
        self._parent = parent
        self._stop = None
        self._session_timeout = session_timeout
        self._request_timeout = request_timeout

        self.objects = None
        self.subscriptions = {}

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        logger.debug("Create client with address=%s and timeout=%s", self._address, self._request_timeout)
        self._client = Client(self._address, timeout=self._request_timeout, watchdog_intervall=self._session_timeout)
        self._stop = asyncio.Event()

    async def loop(self):
        """
        We regularly check the connection to the opc-ua server
        """
        while True:
            try:
                # check the connection state at least every second or dependent on the session timeout
                # we check about 2.5 times within the specified interval (the session_timeout is given in ms)
                await asyncio.wait_for(self._stop.wait(), timeout=min(1, self._session_timeout / 1.2))
            except asyncio.TimeoutError:
                # if the timeout occurs, the timeout occurs
                pass
            except asyncio.CancelledError:
                # if the cancel is raised, the coroutine should stop
                break

            try:
                await self._client.check_connection()
            except Exception:  # pylint: disable=broad-except
                logger.exception("Connection to OPC-UA-Server had an error")
                break

        # disconnect gracefully
        await self.stop()

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        logger.debug("Try to establish OPCUA connection with %s", self._address)

        wait = 0
        while True:
            try:
                await self._client.connect()
                break
            except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror):
                wait = min(60, wait + 1)
                logger.info('Connection to %s refused (retry in %ss)', self._address, wait)
                await asyncio.sleep(wait)

        logger.info("OPCUA connected to %s", self._address)
        self.objects = self._client.nodes.objects
        await self._parent.opcua_start()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if not self._stop.is_set():
            try:
                await self._client.disconnect()
            except asyncio.TimeoutError:
                # OPC-UA is already disconnected
                pass
            except Exception:  # pylint: disable=broad-except:
                logger.exception("Error disconnecting OPC-UA")
            self._stop.set()

    async def write_many(self, data):
        """
        writes variables to opcua
        """
        nodes = []
        values = []
        for node, value, datatype in data:
            nodes.append(node)
            values.append(DataValue(Variant(value, datatype)))
        if not nodes:
            return True
        try:
            delta = time()
            await self._client.write_values(nodes, values)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Problem writing nodes via OPC-UA")
            return False

        delta = (time() - delta) * 1000
        asyncio.create_task(self._parent.opcua_stats_write(len(nodes), delta))
        return True

    async def subscribe(self, nodes, interval):
        """
        subscribe to variable
        """
        if isinstance(nodes, dict):
            nodes = list(self.get_node(name, path) for name, path in nodes.items())

        try:
            subscription = self.subscriptions[interval]
        except KeyError:
            subscription = await self._client.create_subscription(interval, Handler(self._parent, self))
            subscription._call_datachange = MethodType(monkeypatch_call_datachange, subscription)  # pylint: disable=protected-access  # noqa: E501
            self.subscriptions[interval] = subscription

        await subscription.subscribe_data_change(nodes)

    async def get_node(self, name=None, path=None):
        """
        get node object
        """
        try:
            return self._nodes[name]
        except KeyError:
            if path is None:
                return None
            if isinstance(path, (list, tuple)):
                node = await self._client.nodes.objects.get_child(path)
            else:
                node = self._client.get_node(path)
            if name is not None:
                self._nodes[name] = node
            return node


class OPCUAMixin:
    """
    Mixin to add OPC-UA functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if OPCUA:
            self._opcua = OPCUACoroutine(self, **self.opcua_kwargs())

    def _setup(self):
        super()._setup()
        if OPCUA:
            self.aio_manager.register(self._opcua)

    def opcua_kwargs(self):
        """
        return the init kwargs
        """
        return {
            'host': self.iams.address,
        }

    async def opcua_start(self):
        """
        Callback after opcua started
        """

    async def opcua_datachange(self, node, val, data):
        """
        Datachange callback (one per subscribed variable)
        """

    async def opcua_datachanges(self, results, changes):
        """
        Datachanges callback (one per packet)
        """

    async def opcua_write(self, node, value, datatype, sync=True):
        """
        write value to node on opcua-server
        """
        if OPCUA:
            return await self.opcua_write_many([node, value, datatype], sync=sync)

    async def opcua_write_many(self, data, sync=True):
        """
        data is a list or tuple of node, value and datatype
        """
        if OPCUA:
            future = self._opcua.write_many(data)
            if sync:
                return await future
            return asyncio.create_task(future)

    async def opcua_stats_write(self, writes, response_time):
        """
        The numer of written nodes and the response time (in miliseconds) from the OPC-UA server can be processed here
        """

    async def opcua_statuschange(self, code, name, doc):  # pylint: disable=unused-argument
        """
        calles with the status if the status was changed by the opcua client
        """
        if OPCUA:
            if code == StatusCodes.BadShutdown:
                await self._opcua.stop()

    async def opcua_subscribe(self, nodes, interval):
        """
        subscribe to topic
        """
        if OPCUA:
            return await self._opcua.subscribe(nodes, interval)

    async def opcua_node(self, name=None, path=None):
        """
        gets the node object for a path
        """
        if OPCUA:
            return await self._opcua.get_node(name=name, path=path)

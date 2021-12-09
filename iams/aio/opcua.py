#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
opc ua mixin for agents
"""

from types import MethodType
import asyncio
import logging

from iams.aio.interfaces import Coroutine

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

    def __init__(self, agent, coro):
        self.agent = agent
        self.coro = coro

    def datachange_notifications(self, notifications):
        """
        packet datachange notifications
        """
        # pylint: disable=protected-access
        asyncio.run_coroutine_threadsafe(
            self.coro.datachanges(notifications),
            self.coro._loop,
        )


class OPCUACoroutine(Coroutine):  # pylint: disable=too-many-instance-attributes
    """
    OPCUA Coroutine
    """

    def __init__(self, parent, host, port=4840, timeout=15, heartbeat=12.5):  # pylint: disable=too-many-arguments
        logger.debug("Initialize OPCUA coroutine")

        self._address = f"opc.tcp://{host}:{port}/"
        self._client = None
        self._executor = None
        self._heartbeat = heartbeat
        self._loop = None
        self._parent = parent
        self._stop = None
        self._timeout = timeout

        self.handles = {}
        self.objects = None
        self.subscriptions = {}

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        logger.debug("Try to establish OPCUA connection with %s", self._address)
        self._client = Client(self._address, timeout=self._timeout)
        self._executor = executor
        self._loop = asyncio.get_running_loop()
        self._stop = self._loop.create_future()

    async def loop(self):
        """
        loop method contains the business-code
        """
        if self._heartbeat:
            # pylint: disable=protected-access
            while not self._stop.done() and self._client.uaclient._uasocket._thread.is_alive():
                logger.debug("OPCUA for heartbeat")
                try:
                    await asyncio.wait_for(self._stop, timeout=self._heartbeat)
                except asyncio.TimeoutError:
                    # refresh self._stop as it got canceled by wait_for
                    self._stop = self._loop.create_future()
                else:
                    break
                result = await self._parent.opcua_heartbeat()
                logger.debug("OPCUA heartbeat returned %s", result)
                if result in [None, False]:
                    logger.debug("OPCUA: get_objects_node()")
                    await self._loop.run_in_executor(self._executor, self._client.get_objects_node)
        else:
            await asyncio.wait_for(self._stop, timeout=None)

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        wait = 0
        while True:
            try:
                await self._loop.run_in_executor(self._executor, self._client.connect)
                break
            except (ConnectionRefusedError, OSError):
                wait = min(60, wait + 1)
                logger.info('Connection to %s refused (retry in %ss)', self._address, wait)
                await asyncio.sleep(wait)

        logger.info("OPCUA connected to %s", self._address)
        await self._loop.run_in_executor(self._executor, self._client.load_type_definitions)
        self.objects = await self._loop.run_in_executor(self._executor, self._client.get_objects_node)
        await self._parent.opcua_start()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if not self._stop.done():
            self._stop.set_result(None)
            try:
                await self._loop.run_in_executor(self._executor, self._client.disconnect)
            except (TimeoutError, AttributeError):
                pass

    async def write_many(self, data):
        """
        writes variables to opcua
        """
        nodes = []
        values = []
        for node, value, datatype in data:
            nodes.append(node)
            values.append(DataValue(Variant(value, datatype)))

        await self._loop.run_in_executor(
            self._executor,
            self._client.set_values,
            nodes,
            values,
        )

    async def datachanges(self, notifications):
        """
        datachanges
        """
        try:
            results = []
            for node, val, data in notifications:
                logger.debug("%s changed it's value to %s", node, val)
                results.append(await self._parent.opcua_datachange(node, val, data))
            await self._parent.opcua_datachanges(results)
        except Exception:  # pylint: disable=broad-except
            logger.exception("error evaluating datachanges")

    async def subscribe(self, nodes, interval):
        """
        subscribe to variable
        """
        try:
            subscription = self.subscriptions[interval]
        except KeyError:
            # pylint: disable=protected-access
            subscription = await self._loop.run_in_executor(
                self._executor,
                self._client.create_subscription,
                interval,
                Handler(self._parent, self),
            )
            subscription._call_datachange = MethodType(monkeypatch_call_datachange, subscription)
            self.subscriptions[interval] = subscription

        handle = subscription.subscribe_data_change(nodes)
        try:
            for node in nodes:
                self.handles[node] = (subscription, handle)
        except TypeError:
            self.handles[nodes] = (subscription, handle)
        return None

    async def get_node(self, path):
        """
        get node object
        """
        if isinstance(path, (list, tuple)):
            return await self._loop.run_in_executor(
                self._executor,
                self.objects.get_child,
                path,
            )
        return await self._loop.run_in_executor(
            self._executor,
            self._client.get_node,
            path,
        )


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

    async def opcua_datachanges(self, results):
        """
        Datachanges callback (one per packet)
        """

    async def opcua_write(self, node, value, datatype, sync=False):
        """
        write value to node on opcua-server
        """
        if OPCUA:
            future = self._opcua.write_many([node, value, datatype])
            if sync:
                await future
            else:
                asyncio.create_task(future)

    async def opcua_write_many(self, data, sync=False):
        """
        data is a list or tuple of node, value and datatype
        """
        if OPCUA:
            future = self._opcua.write_many(data)
            if sync:
                await future
            else:
                asyncio.create_task(future)

    async def opcua_subscribe(self, nodes, interval):
        """
        subscribe to topic
        """
        if OPCUA:
            return await self._opcua.subscribe(nodes, interval)

    async def opcua_node(self, path):
        """
        gets the node object for a path
        """
        if OPCUA:
            return await self._opcua.get_node(path)

    async def opcua_heartbeat(self):
        """
        talk to the opc-ua server in regular intervals
        """

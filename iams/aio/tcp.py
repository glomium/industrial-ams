#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mixins to establish tcp interfaces
"""

from datetime import datetime
import asyncio
import logging

from iams.aio.interfaces import Coroutine


logger = logging.getLogger(__name__)


class TCPCoroutine(Coroutine):  # pylint: disable=too-many-instance-attributes
    """
    Coroutine to open a TCP writer and reader
    """

    def __init__(self, parent, host, port, timeout=None, heartbeat=None, limit=None):  # pylint: disable=too-many-arguments  # noqa: E501
        logger.debug("Initialize TCP coroutine")

        if isinstance(timeout, (list, tuple)) and len(timeout) == 2:
            self._read_timeout = timeout[0]
            self._write_timeout = timeout[1]
        else:
            self._read_timeout = timeout
            self._write_timeout = timeout

        self._heartbeat = heartbeat
        self._host = host
        self._last = None
        self._limit = limit
        self._parent = parent
        self._port = port
        self._reader = None
        self._stop = None
        self._task = None
        self._writer = None

    async def start(self):
        """
        start method is awaited once, after the setup were concluded
        """
        wait = 0
        while True:
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port, limit=self._limit),
                    timeout=self._read_timeout,
                )
                break
            except (ConnectionRefusedError, asyncio.TimeoutError):
                wait = min(60, wait + 1)
                logger.info('Connection to %s:%s refused (retry in %ss)', self._host, self._port, wait)
                await asyncio.sleep(wait)

        if self._heartbeat:
            self._task = asyncio.create_task(self.heartbeat())
        self._stop = self._loop.create_future()

    async def heartbeat(self):
        """
        methods that writes on a regular basis
        """
        self._last = datetime.now()
        while not self._stop.done():
            delay = (self._last - datetime.now()).total_seconds() + self._heartbeat
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                try:
                    response = await self._parent.tcp_heartbeat()
                except Exception:  # pylint: disable=broad-except
                    logger.exception()
                else:
                    if response in {None, True}:
                        self._last = datetime.now()
        self.stop()

    async def loop(self):
        """
        loop method contains the business-code
        """
        logger.info("TCP reader started")

        while not self._stop.done():
            try:
                data = await asyncio.wait_for(self.read(), timeout=self._read_timeout)
            except asyncio.TimeoutError:
                break

            if data == b'':
                break

            try:
                await self._parent.tcp_process_data(data)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Error in tcp_process_data")
                self.stop()

        logger.info("TCP reader stopped")

    async def read(self):
        """
        read data from reader (might be overwritten by client)
        """
        return await self._reader.read()

    async def write(self, data, timeout=None):
        """
        write data in tcp channel
        """
        self._writer.write(data)
        try:
            await asyncio.wait_for(self._writer.drain, timeout=(timeout or self._write_timeout))
        except asyncio.TimeoutError:
            self.stop()
            return False
        self._last = datetime.now()
        return True

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if self._task is not None:
            self._task.cancel()
        if not self._stop.done():
            self._stop.set_result(True)


class TCPMixin:
    '''
    Mixin to add TCP functionality to agents
    '''

    TCP_PORT = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.TCP_PORT is not None, "TCP_PORT needs to be set on %s" % self.__class__.__qualname__
        self._tcp = self.tcp_get_coroutine()

    def _setup(self):
        super()._setup()
        self.aio_manager.register(self._tcp)

    def tcp_get_coroutine(self):
        '''
        returns a tcpcoroutine
        '''
        return TCPCoroutine(self, **self.tcp_get_kwargs())

    def tcp_get_kwargs(self):
        '''
        returns the keyword arguments to configure a tcp coroutine
        '''
        return {
            'host': self.iams.address,
            'port': self.iams.port or self.TCP_PORT,
        }

    async def tcp_write(self, data, timeout=None, sync=True) -> None:
        """
        write data over tcp
        """
        future = self._tcp.write(data, timeout=timeout)
        if sync:
            await future
        else:
            asyncio.create_task(future)

    async def tcp_process_data(self, data) -> None:
        """
        every packet received via the TCP socket will be passed as data to this callback

        this function needs to be implemented
        """
        raise NotImplementedError("tcp_process_data needs to be implemented on %s" % self.__class__.__qualname__)

    async def tcp_heartbeat(self) -> None:
        """
        if a heartbeat is set this function is called regularly
        """

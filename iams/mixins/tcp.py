#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import socket
import time

from queue import Empty
from queue import Queue

from .event import EventMixin


logger = logging.getLogger(__name__)


class TCPMixin(EventMixin):
    TCP_BUFFER = 1024
    TCP_HEARTBEAT = None
    TCP_PORT = None
    TCP_TIMEOUT = 15

    def __init__(self, *args, **kwargs) -> None:
        assert self.TCP_PORT is not None, "TCP_PORT needs to be set on %s" % self.__class__.__qualname__
        super().__init__(*args, **kwargs)
        logger.debug("TCP socket class initialized")
        self._tcp_queue = Queue()

    def _pre_setup(self):
        """
        """
        assert self._iams.address is not None, 'Must define IAMS_ADDRESS in environment'

        while not self._stop_event.is_set():
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.TCP_TIMEOUT)
                self._socket.connect((self._iams.address, self._iams.port or self.TCP_PORT))
                break
            except (ConnectionRefusedError, socket.timeout, OSError):
                logger.info("Host %s:%s not reachable", self._iams.address, self._iams.port or self.TCP_PORT)
                time.sleep(5)
        logger.debug("TCP socket connected to %s:%s", self._iams.address, self._iams.port or self.TCP_PORT)

        if self._stop_event.is_set():
            raise SystemExit

        self._executor.submit(self._tcp_reader)
        self._executor.submit(self._tcp_writer)
        return super()._pre_setup()

    def _tcp_reader(self):
        logger.debug("TCP reader started")
        while not self._socket._closed:
            try:
                data = self._socket.recv(self.TCP_BUFFER)
                if self.tcp_process_data(data):
                    self._loop_event.clear()
            except (OSError, socket.timeout, ConnectionResetError):
                logger.info("Connection Error - Shutdown", exc_info=True)
                self.stop()
                break
            except Exception:
                logger.exception("Error in parent.process_data")
                self.stop()
                break
        logger.debug("TCP reader stopped")

    def _tcp_writer(self):

        logger.debug("TCP writer started")
        heartbeat = False

        while not self._socket._closed:

            if heartbeat:
                self.tcp_heartbeat()
                heartbeat = False

            try:
                data = self.queue.get(timeout=self.TCP_HEARTBEAT)
            except Empty:
                heartbeat = True
                continue

            logger.debug("TCP writer sending %s", data)

            try:
                self._socket.send(data)
            except (OSError, BrokenPipeError):
                logger.info("Connection Error - Shutdown", exc_info=True)
                self.stop()
                break

        logger.debug("TCP writer stopped")

    def stop(self) -> None:
        logger.debug("Closing TCP socket")
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except (OSError, AttributeError):
            pass
        super().stop()

    def tcp_write(self, data):
        self._writer.queue.put(data)

    def tcp_heartbeat(self):
        pass

    def tcp_process_data(self, data) -> bool:
        raise NotImplementedError("A loop method needs to be implemented on %s" % self.__class__.__qualname__)

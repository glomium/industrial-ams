#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import socket
import time

from queue import Empty
from queue import Queue
from threading import Event
from threading import Thread

from .event import EventMixin


logger = logging.getLogger(__name__)


class TCPWriter(Thread):
    def __init__(self, parent, socket, timeout) -> None:
        self.parent = parent
        self.socket = socket
        self.timeout = timeout
        self.queue = Queue()
        super().__init__()
        self.daemon = True

    def run(self):
        logger.debug("TCPWriter started")
        while not self.socket._closed:
            try:
                data = self.queue.get(timeout=self.timeout)
            except Empty:
                self.parent.heartbeat_tcp()
                continue
            except Exception:
                logger.exception("Error in parent.request_state")
                raise

            logger.debug("TCPWriter sending %s", data)
            try:
                self.socket.send(data)
            except (OSError, BrokenPipeError):
                logger.info("Connection Error - Shutdown", exc_info=True)
                self.parent.stop()
                break
        logger.debug("TCPWriter stopped")


class TCPReader(Thread):
    def __init__(self, parent, socket, tcp_buffer) -> None:
        self.parent = parent
        self.socket = socket
        self.buffer = tcp_buffer
        super().__init__()
        self.daemon = True

    def run(self):
        logger.debug("TCPReader started")
        while not self.socket._closed:
            try:
                data = self.socket.recv(self.buffer)
                if self.parent.process_data(data):
                    self.parent._loop_event.clear()
            except (OSError, socket.timeout, ConnectionResetError):
                logger.info("Connection Error - Shutdown", exc_info=True)
                self.parent.stop()
                break
            except Exception:
                logger.exception("Error in parent.process_data")
                self.parent.stop()
                break
        logger.debug("TCPReader stopped")


class TCPMixin(EventMixin):
    TCP_PORT = None
    TCP_TIMEOUT = 15
    TCP_BUFFER = 1024

    def __init__(self, *args, **kwargs) -> None:
        assert self.TCP_PORT is not None, "TCP_PORT needs to be set on %s" % self.__class__.__qualname__
        super().__init__(*args, **kwargs)
        logger.debug("TCP socket class initialized")
        self._read_event = Event()

    def _pre_setup(self):
        """
        """
        assert self._framework_agent.address is not None, 'Must define CCM_ADDRESS in environment'

        while True:
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.TCP_TIMEOUT)
                self._socket.connect((self._framework_agent.address, self.TCP_PORT))
                break
            except (ConnectionRefusedError, socket.timeout, OSError):
                logger.info("Host %s:%s not reachable", self._framework_agent.address, self.TCP_PORT)
                time.sleep(5)
        logger.debug("TCP socket connected to %s:%s", self._framework_agent.address, self.TCP_PORT)
        if self.TCP_TIMEOUT > 10:
            timeout = self.TCP_TIMEOUT - 2
        else:
            timeout = 0.8 * self.TCP_TIMEOUT

        self._reader = TCPReader(self, self._socket, self.TCP_BUFFER)
        self._reader.start()

        self._writer = TCPWriter(self, self._socket, timeout)
        self._writer.start()

        return super()._pre_setup()

    def stop(self) -> None:
        logger.debug("Stop requested")
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except (OSError, AttributeError):
            pass
        super().stop()

    def write(self, data):
        self._writer.queue.put(data)

    def heartbeat_tcp(self):
        pass

    def process_data(self, data) -> bool:
        raise NotImplementedError("A loop method needs to be implemented on %s" % self.__class__.__qualname__)

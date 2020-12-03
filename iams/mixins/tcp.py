#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import socket

from queue import Empty
from queue import Queue

from .event import EventMixin


logger = logging.getLogger(__name__)


class TCPReadMixin(EventMixin):
    TCP_BUFFER = 1024
    TCP_PORT = None
    TCP_TIMEOUT = 15

    def __init__(self, *args, **kwargs) -> None:
        assert self.TCP_PORT is not None, "TCP_PORT needs to be set on %s" % self.__class__.__qualname__
        super().__init__(*args, **kwargs)
        logger.debug("%s initialized", self.__class__.__qualname__)

    def _pre_setup(self):
        """
        """
        assert self._iams.address is not None, 'Must define IAMS_ADDRESS in environment'

        wait = 0
        while not self._stop_event.is_set():
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.TCP_TIMEOUT)
                self._socket.connect((self._iams.address, self._iams.port or self.TCP_PORT))
                break
            except (ConnectionRefusedError, socket.timeout, OSError):
                wait += 1
                if wait > 60:
                    wait = 60
                logger.info(
                    "%s:%s not reachable (retry in %ss)",
                    self._iams.address,
                    self._iams.port or self.TCP_PORT,
                    wait,
                )
                self._stop_event.wait(wait)
        logger.debug("TCP socket connected to %s:%s", self._iams.address, self._iams.port or self.TCP_PORT)

        if self._stop_event.is_set():
            raise SystemExit

        self._executor.submit(self._tcp_reader)
        super()._pre_setup()

    def _tcp_reader(self):
        logger.info("TCP reader started")
        while not self._socket._closed:
            try:
                data = self._socket.recv(self.TCP_BUFFER)
                # connection was closed
                if not data:
                    self.stop()
                    break
                if self.tcp_process_data(data):
                    self._loop_event.set()
            except (OSError, socket.timeout, ConnectionResetError):
                logger.info("Connection Error - Shutdown", exc_info=True)
                self.stop()
                break
            except Exception:
                logger.exception("Error in tcp_process_data")
                self.stop()
                break
        logger.info("TCP reader stopped")

    def _teardown(self):
        super()._teardown()
        logger.debug("Closing TCP socket")
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except (OSError, AttributeError):
            pass

    def tcp_process_data(self, data) -> bool:
        """
        every packet received via the TCP socket will be passed as data to this callback

        this function needs to be implemented
        """
        raise NotImplementedError("tcp_process_data needs to be implemented on %s" % self.__class__.__qualname__)


class TCPMixin(TCPReadMixin):
    """
    Adds TCP/IP communication to agent.
    Address is automatically read via agent configuration
    Needs to be configured with a TCP_PORT attribute.
    """
    TCP_HEARTBEAT = None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tcp_queue = Queue()

    def _pre_setup(self):
        """
        """
        super()._pre_setup()
        self._executor.submit(self._tcp_writer)

    def tcp_heartbeat(self):
        """
        TCP_HEARTBEAT is used as an interval.
        if no data was send this function is triggered and can, for example send a packet to test the connection
        """
        pass

    def _tcp_writer(self):

        logger.info("TCP writer started")
        heartbeat = False

        while not self._socket._closed:

            if heartbeat:
                self.tcp_heartbeat()
                heartbeat = False

            try:
                data = self._tcp_queue.get(timeout=self.TCP_HEARTBEAT)
            except Empty:
                heartbeat = True
                continue

            if data:
                logger.debug("TCP writer sending %s", data)
                try:
                    self._socket.sendall(data)
                except (OSError, BrokenPipeError):
                    logger.info("Connection Error - Shutdown", exc_info=True)
                    self.stop()
                    break

        logger.info("TCP writer stopped")

    def _teardown(self):
        super()._teardown()
        self._tcp_queue.put(b'')

    def tcp_write(self, data):
        """
        use this function to send data to the connected device
        """
        self._tcp_queue.put(data)

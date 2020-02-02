#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging
import time

from opcua import Client
from opcua import ua
from queue import Empty
from queue import Queue


logger = logging.getLogger(__name__)


class OPCUABaseMixin(object):

    def __call__(self):
        try:
            super().__call__()
        finally:
            if hasattr(self, 'client'):
                try:
                    self.client.disconnect()
                except (TimeoutError):
                    pass

    def _pre_setup(self):
        super()._pre_setup()
        assert self._agent.address is not None, 'Must define CCM_ADDRESS in environment'

        logger.debug("creating opcua-client to %s:%s", self._agent.address, self._port)
        self.client = Client("opc.tcp://%s:%s/" % (self._agent.address, self._port), timeout=10)

        # load definition of server specific structures/extension objects
        self._agent.set_connecting()

        sleep = 0
        while True:
            if sleep < 60:
                sleep += 5
            try:
                self.client.connect()
                break
            except ConnectionRefusedError:
                logger.exception('Connection to %s:%s refused', self._agent.address, self._port)
            logger.debug("sleeping %s seconds", sleep)
            time.sleep(sleep)

        self.client.load_type_definitions()
        # self.root = self.client.get_root_node()
        self.objects = self.client.get_objects_node()

    def _loop(self):
        self._agent.set_idle()
        while self.client.uaclient._uasocket._thread.isAlive():
            self.loop()

    def loop(self):
        raise NotImplementedError("A loop method must be implemented")


class OPCUAMixin(OPCUABaseMixin):
    def _pre_setup(self):
        super()._pre_setup()
        self.queue = Queue()
        self.subscription_handler = self.client.create_subscription(250, self)
        self.callbacks = {}

    def loop(self):
        try:
            node, value, dt = self.queue.get(timeout=5)
        except Empty:
            return None
        node.set_value(ua.DataValue(ua.Variant(value, dt)))

    def create_subscription(self, node, callback):
        if node not in self.callbacks:
            self.subscription_handler.subscribe_data_change(node)
            self.callbacks[node] = callback

    def set_value(self, node, value, dt):
        self.queue.put((node, value, dt))

    def datachange_notification(self, node, value, event):
        try:
            callback = self.callbacks[node]
        except KeyError:
            logger.exception("%s not found in callbacks" % node)
            return None
        callback(value)

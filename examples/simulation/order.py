#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging

from logging.config import dictConfig
# from math import sqrt

# import grpc

# from google.protobuf.empty_pb2 import Empty

from iams.helper import get_logging_config
from iams.interfaces import Agent
from iams.interfaces.market import OrderInterface
# from iams.market import Step
from iams.market import MarketMasterInterface
from iams.proto import market_pb2
# from iams.utils.auth import permissions

# import example_pb2
import example_pb2_grpc


logger = logging.getLogger(__name__)


class OrderClass(OrderInterface):

    def load(self, config):
        ability1 = [market_pb2.Ability(name="test1")]
        ability2 = [market_pb2.Ability(name="test2")]
        ability3 = [market_pb2.Ability(name="test3")]
        ability4 = [market_pb2.Ability(name="test4")]

        data = [
            market_pb2.Step(name='a', edges=['c'], abilities=ability1, group="a"),
            market_pb2.Step(name='b', edges=['c'], abilities=ability1, group="a"),
            market_pb2.Step(name='c', edges=['d'], abilities=ability2),
            market_pb2.Step(name='d', edges=['e'], abilities=ability3),
            market_pb2.Step(name='e', abilities=ability4),
        ]
        for step in data:
            self.instance.steps.append(step)

        logger.info('config: %s', config)


class Servicer(example_pb2_grpc.OrderServicer):

    def __init__(self, parent):
        self.parent = parent


class Order(MarketMasterInterface, Agent):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servicer = Servicer(self)

    def grpc_setup(self):
        self._grpc.add(example_pb2_grpc.add_OrderServicer_to_server, self.servicer)

    def configure(self):
        self._iams.update_position(self._config["position"])

    def market_current_step(self):
        """
        returns the current position (agent name) and step (integer)
        """
        return 0

    def market_update_config(self, *kwargs):
        raise NotImplementedError

    def market_get_order_class(self):
        return OrderClass

    def market_get_recipe(self):
        raise NotImplementedError

    def order_started(self):
        raise NotImplementedError

    def order_reassign(self):
        raise NotImplementedError

    def order_reassigned(self):
        raise NotImplementedError

    def order_canceled(self):
        raise NotImplementedError

    # def order_skip_step(self, step):
    #     raise NotImplementedError

    def order_start_step(self):
        raise NotImplementedError

    def order_next_step(self):
        raise NotImplementedError

    def order_finish_step(self):
        raise NotImplementedError

    def order_cancel(self):
        raise NotImplementedError

    def order_finished(self):
        raise NotImplementedError

    def topology_default_edge(self):
        return None


if __name__ == "__main__":
    dictConfig(get_logging_config(["iams"], logging.DEBUG))
    run = Order()
    run()

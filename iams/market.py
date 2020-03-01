#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import concurrent
import logging

from abc import ABC
from abc import abstractmethod
from enum import auto
from enum import Enum

import grpc

from .proto import market_pb2
from .proto import market_pb2_grpc


logger = logging.getLogger(__name__)


class RootStates(Enum):
    APPLY = auto()  # order is applying to agents
    SELECT = auto()  # order is selecting one agent
    WAIT = auto()  # order triggers one agent
    START = auto()  # Callback function
    RUNNING = auto()  # Order is currently executed
    FINISH = auto()  # Callback function
    CANCEL = auto()  # Callback function
    SHUTDOWN = auto()  # order agent is waiting to be killed by docker


class OrderNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):
    pass


class OrderCallbackServicer(market_pb2_grpc.OrderCallbackServicer):
    pass


class ProxyNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):
    pass


class ProxyCallbackServicer(market_pb2_grpc.OrderCallbackServicer):
    pass


class RootInterface(ABC):
    """
    Has the steps, asks agents to produce the steps and tracks the process
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._order_state = RootStates.APPLY
        self._order_applications = {}

    def _grpc_setup(self):
        super()._grpc_setup()
        self._order_negotiate_servicer = OrderNegotiateServicer()
        self._grpc.add(
            market_pb2_grpc.add_OrderNegotiateServicer_to_server,
            self._order_negotiate_servicer,
        )

    def setup(self):
        config = self.order_update_config(10)
        if config is not None:
            logger.debug("_config is overwritten with config from service")
            self._config = config

    def simulation_start(self):
        self._loop_apply()

    def _loop(self):
        while not self._stop_event.is_set():
            logger.debug("Running loop from state %s", self.state)

            if self.state == RootStates.APPLY:
                self.loop_apply()

            elif self.state == RootStates.SELECT:
                self.loop_select()

            elif self.state == RootStates.START:
                if not self._iams.simulation:
                    self.order_started()
                self.state = RootStates.RUNNING

            elif self.state == RootStates.RUNNING:
                self.loop_running()

            elif self.state == RootStates.FINISH:
                # shedule shutdown of agent (in 60 seconds to avoid interference with wait in loop_select)
                if self._iams.simulation:
                    self._simulation.schedule(60, '_loop')
                else:
                    self.order_finished()
                self.state = RootStates.SHUTDOWN

            elif self.state == RootStates.CANCEL:
                # shedule shutdown of agent (in 60 seconds to avoid interference with wait in loop_select)
                if self._iams.simulation:
                    self._simulation.schedule(60, '_loop')
                else:
                    self.order_canceled()
                self.state = RootStates.SHUTDOWN

            elif self.state == RootStates.SHUTDOWN:
                self._iams.call_destroy()
                logger.debug("Waiting for the shutdown signal from docker")
                self._stop_event.wait(30)

            else:
                logger.critical("State %s not defined!", self.state)
                break

            if self._iams.simulation is False:
                self._loop_event.clear()

    def loop_apply(self):
        """
        """
        # get a list of agents
        agents = []
        for labels in self.order_agent_labels(self):
            for agent in self._iams.get_agents(labels):
                agents.append(agent.name)

        self._order_applications = {}

        futures = []
        eta, steps = self.order_get_data()
        request = market_pb2.OrderInfo(steps=steps, eta=eta)
        for agent in agents:
            futures.append(self._executor.submit(self._order_application, request, agent))
        concurrent.futures.wait(futures)

        self.state = RootStates.SELECT
        self._loop_select()

    def _order_application(self, request, agent):
        """
        this runs in a seperate thread. it connects to an agent and adds its price and cost
        to the _order_applications dictionary
        """
        try:
            logger.debug("calling apply from OrderNegotiateStub on %s", agent)
            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderNegotiateStub(channel)
                response = stub.apply(request, timeout=20)
        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return None

        total_time = response.time_production + response.time_transport + response.time_queue
        total_cost = response.cost_production + response.cost_transport

        if total_cost <= 0.0 or total_time <= 0.0:
            logger.critical(
                "%s response not accepted (total_cost: %s, total_time: %s)",
                agent, total_cost, total_time,
            )
            return None

        logger.debug("%s accepted the order with cost %s and time %s", agent, total_cost, total_time)
        with self._lock:
            self._order_applications[agent] = {
                "cost": total_cost,
                "time": total_time,
            }

    def loop_select(self):
        """
        """
        if not self._order_applications:
            logger.info("No agent applied for this order - wait 60 seconds and retry")
            self.state = RootStates.APPLY

            if self._iams.simulation:
                self._simulation.schedule(60, '_loop_apply')
            else:
                self._loop_event.wait(60)

        # select one order
        with self._lock:
            agent = None
            cost = 0.0
            eta = 0.0
            for key, value in self._order_applications.items():
                if agent is None or value["cost"] < cost:
                    agent = key
                    cost = value["cost"]
                    eta = value["time"]

            if agent is None:
                return None

            # delete selected order from list
            del self._applications[agent]

        logger.info(
            "Agent %s selected with cost %s and eta %s",
            agent,
            cost,
            eta,
        )

        eta, steps = self.order_get_data()
        request = market_pb2.OrderInfo(steps=steps, eta=eta)
        try:
            logger.debug("calling assign from OrderNegotiateStub on %s", agent)
            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderNegotiateStub(channel)
                response = stub.assign(request, timeout=20)
        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return None

        total_time = response.time_production + response.time_transport + response.time_queue
        total_cost = response.cost_production + response.cost_transport

        logger.debug("%s assigned the order with cost %s and time %s", agent, total_cost, total_time)

        self.state = RootStates.STARTING

    def loop_running(self):
        """
        """
        if self._iams.simulation is False:
            logger.debug("waiting for event")
            self._loop_event.wait()

    @abstractmethod
    def order_update_config(self, retries=0):
        """
        receive order data from service
        """
        pass

    @abstractmethod
    def order_get_data(self):
        """
        return eta and steps
        """
        pass

    @abstractmethod
    def order_agent_labels(self):
        """
        iterator, which generates a list of labels which is used to filter docker
        services for devices which can execute this order
        """
        pass

    @abstractmethod
    def order_started(self):
        pass

    @abstractmethod
    def order_finished(self):
        """
        """
        pass

    @abstractmethod
    def order_canceled(self):
        """
        """
        pass


class SplitInterface(ABC):
    """
    Splits the steps by ability and connects to different agents
    """

    def _grpc_setup(self):
        super()._grpc_setup()
        self._order_callback_servicer = ProxyCallbackServicer()
        self._order_negotiate_servicer = ProxyNegotiateServicer()
        self._grpc.add(
            market_pb2_grpc.add_OrderCallbackServicer_to_server,
            self._order_callback_servicer,
        )
        self._grpc.add(
            market_pb2_grpc.add_OrderCallbackServicer_to_server,
            self._order_negotiate_servicer,
        )

    @abstractmethod
    def order_validate(self, order, steps, eta, start):
        """
        """
        pass


class ExecuteInterface(ABC):
    """
    Executes the steps (or a part of it)
    """

    def _grpc_setup(self):
        super()._grpc_setup()
        self._order_callback_servicer = OrderCallbackServicer()
        self._grpc.add(
            market_pb2_grpc.add_OrderCallbackServicer_to_server,
            self._order_callback_servicer,
        )

    @abstractmethod
    def order_validate(self, order, steps, eta, start):
        """
        """
        pass

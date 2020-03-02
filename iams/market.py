#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import concurrent
import logging

from abc import ABC
from abc import abstractmethod
from enum import auto
from enum import Enum

import grpc

from google.protobuf.empty_pb2 import Empty

from iams.utils.auth import permissions

from .proto import market_pb2
from .proto import market_pb2_grpc


logger = logging.getLogger(__name__)


# === ROOT ====================================================================


class RootStates(Enum):
    APPLY = auto()  # order is applying to agents
    SELECT = auto()  # order is selecting one agent
    WAIT = auto()  # order triggers one agent
    START = auto()  # Callback function
    RUNNING = auto()  # Order is currently executed
    FINISH = auto()  # Callback function
    CANCEL = auto()  # Callback function
    SHUTDOWN = auto()  # order agent is waiting to be killed by docker


class OrderCallbackServicer(market_pb2_grpc.OrderCallbackServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True, has_groups=["web"])
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_cancel():
            self.parent._order_state = RootStates.CANCEL
            if self._iams.simulation:
                self._simulation.schedule(0.0, '_loop')
            else:
                self.parent._loop_event.set()
            return Empty()
        else:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")

    @permissions(has_agent=True)
    def start_step(self, request, context):
        logger.debug("%s.start_step was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_start_step():
            return Empty()
        else:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")

    @permissions(has_agent=True)
    def finish_step(self, request, context):
        logger.debug("%s.finish_step was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_finish_step():
            return Empty()
        else:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")


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
        self._grpc.add(
            market_pb2_grpc.add_OrderCallbackServicer_to_server,
            OrderCallbackServicer(self),
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
            logger.debug("Running loop from state %s", self._order_state)

            if self._order_state == RootStates.APPLY:
                self.loop_apply()

            elif self._order_state == RootStates.SELECT:
                self.loop_select()

            elif self._order_state == RootStates.START:
                if not self._iams.simulation:
                    self.order_started()
                self._order_state = RootStates.RUNNING

            elif self._order_state == RootStates.RUNNING:
                self.loop_running()

            elif self._order_state == RootStates.FINISH:
                # shedule shutdown of agent (in 60 seconds to avoid interference with wait in loop_select)
                if self._iams.simulation:
                    self._simulation.schedule(60, '_loop')
                else:
                    self.order_finished()
                self._order_state = RootStates.SHUTDOWN

            elif self._order_state == RootStates.CANCEL:
                # shedule shutdown of agent (in 60 seconds to avoid interference with wait in loop_select)
                if self._iams.simulation:
                    self._simulation.schedule(60, '_loop')
                else:
                    self.order_canceled()
                self._order_state = RootStates.SHUTDOWN

            elif self._order_state == RootStates.SHUTDOWN:
                self._iams.call_destroy()
                logger.debug("Waiting for the shutdown signal from docker")
                self._stop_event.wait(30)

            else:
                logger.critical("State %s not defined!", self._order_state)
                break

            if self._iams.simulation is False:
                self._loop_event.clear()

    def loop_apply(self):
        """
        """
        # get a list of agents
        agents = []
        for labels in self.order_agent_labels():
            for agent in self._iams.get_agents(labels):
                agents.append(agent.name)

        self._order_applications = {}

        futures = []
        eta, steps = self.order_get_data()
        request = market_pb2.OrderInfo(steps=steps, eta=eta)
        for agent in agents:
            futures.append(self._executor.submit(self._order_application, request, agent))
        concurrent.futures.wait(futures)

        self._order_state = RootStates.SELECT
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
            self._order_state = RootStates.APPLY

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
                c = self.order_cost_function(value["cost"], value["time"])
                if agent is None or c < cost:
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

        self._order_state = RootStates.STARTING

    def order_cost_function(self, value, time):
        """
        return eta and steps
        """
        return value

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
        """
        runs if the order was assigned (callback with MES to start it)
        """
        pass

    @abstractmethod
    def order_finished(self):
        """
        runs if all steps are done (callback with MES to start it)
        """
        pass

    @abstractmethod
    def order_cancel(self):  # from servicer
        """
        callback to cancel the order
        """
        pass

    @abstractmethod
    def order_canceled(self):
        """
        cleanup after order cancelling
        """
        pass

    @abstractmethod
    def order_start_step(self):  # from servicer
        """
        report start execution of a step
        """
        pass

    @abstractmethod
    def order_finish_step(self):  # from servicer
        """
        report end execution of a step
        """
        pass


# === INTERMEDIATE ============================================================


class ProxyNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def apply(self, request, context):
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)

    @permissions(has_agent=True)
    def assign(self, request, context):
        logger.debug("%s.assign was called by %s", self.__class__.__qualname__, context._agent)

    @permissions(has_agent=True)
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)


class ProxyCallbackServicer(market_pb2_grpc.OrderCallbackServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        raise NotImplementedError

    @permissions(has_agent=True)
    def start_step(self, request, context):
        logger.debug("%s.start_step was called by %s", self.__class__.__qualname__, context._agent)

    @permissions(has_agent=True)
    def finish_step(self, request, context):
        logger.debug("%s.finish_step was called by %s", self.__class__.__qualname__, context._agent)


class IntermediateInterface(ABC):
    """
    Splits the steps by ability and connects to different agents
    """

    def _grpc_setup(self):
        super()._grpc_setup()
        self._grpc.add(
            market_pb2_grpc.add_OrderCallbackServicer_to_server,
            ProxyCallbackServicer(self),
        )
        self._grpc.add(
            market_pb2_grpc.add_OrderNegotiateServicer_to_server,
            ProxyNegotiateServicer(self),
        )

    @abstractmethod
    def order_validate(self, order, steps, eta, start):
        """
        """
        pass

    @abstractmethod
    def order_agent_labels(self):
        """
        iterator, which generates a list of labels which is used to filter docker
        services for devices which can execute this order
        """
        pass


# === EXCECUTION ==============================================================


class OrderNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def apply(self, request, context):
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
        return self.validate(request, context, False)

    @permissions(has_agent=True)
    def assign(self, request, context):
        logger.debug("%s.assign was called by %s", self.__class__.__qualname__, context._agent)
        order = request.order or context._agent
        response = self.validate(request, context, True)
        if self.parent.order_start(order, request.steps):
            return response
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Error assigning order %s" % order)

    @permissions(has_agent=True)
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        order = request.order or context._agent
        if self.parent.order_cancel(order):
            return Empty()
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Error cancelling order %s" % order)

    def validate(self, request, context, start):
        order = request.order or context._agent
        steps = request.steps
        eta = request.eta

        valid, cost_p, cost_t, time_p, time_t, time_q = self.parent.order_validate(order, steps, eta, start)
        if not valid:
            context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")

        return market_pb2.OrderCosts(
            production_cost=cost_p,
            production_time=time_p,
            queue_time=time_q,
            transport_cost=cost_t,
            transport_time=time_t,
        )


class ExecuteInterface(ABC):
    """
    Executes the steps (or a part of it)
    """

    def _grpc_setup(self):
        super()._grpc_setup()
        self._grpc.add(
            market_pb2_grpc.add_OrderNegotiateServicer_to_server,
            OrderNegotiateServicer(self),
        )

    @abstractmethod
    def order_validate(self, order, steps, eta, start):  # from servicer
        """
        """
        pass

    @abstractmethod
    def order_start(self, order, steps):  # from servicer
        """
        """
        pass

    @abstractmethod
    def order_cancel(self, order):  # from servicer
        """
        """
        pass

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

    @permissions(has_agent=True)
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
    def finish_step(self, request: market_pb2.Step, context) -> Empty:
        logger.debug("%s.finish_step was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_finish_step(request):
            return Empty()
        else:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")

    @permissions(has_agent=True)
    def next_step(self, request: Empty, context) -> Empty:
        logger.debug("%s.next_step was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_next_step(request):
            return Empty()
        else:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")

    @permissions(has_agent=True)
    def start_step(self, request: market_pb2.Step, context) -> Empty:
        logger.debug("%s.start_step was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_start_step(request):
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
        self._order_steps = {}

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
        self.loop_apply()

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

        # currently the eta is not applied propperly. ideally we sort the steps from
        # last to first and calculate the eta backwards. thus we could also implement
        # least time and least cost algorithms (when eta is negative or small, the costs
        # might be neglectable and for high eta we optimise the production cost)

        request = market_pb2.OrderInfo(order=self._iams.agent, eta=eta, steps=steps)

        for agent in agents:
            futures.append(self._executor.submit(self._order_application, request, agent))
        concurrent.futures.wait(futures)

        self._order_state = RootStates.SELECT
        self.loop_select()

    def _order_application(self, request, agent):
        """
        this runs in a seperate thread. it connects to an agent and adds its price and cost
        to the _order_applications dictionary
        """
        path = []
        production_cost = 0.0
        production_time = 0.0
        queue_cost = 0.0
        queue_time = 0.0
        transport_cost = 0.0
        transport_time = 0.0
        try:
            logger.debug("calling apply from OrderNegotiateStub on %s", agent)
            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderNegotiateStub(channel)
                for response in stub.apply(request, timeout=20):
                    if not response.info:
                        logger.critical("Response from %s is missing info attribute", agent)
                    if not response.cost:
                        logger.critical("Response from %s is missing cost attribute", agent)

                    path.append((response.agent or agent, response.info.steps))
                    production_cost += response.cost.production_cost
                    production_time += response.cost.production_time
                    queue_cost += response.cost.queue_cost
                    queue_time += response.cost.queue_time
                    transport_cost += response.cost.transport_cost
                    transport_time += response.cost.transport_time

        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return None

        total_time = production_time + transport_time + queue_time
        total_cost = production_cost + transport_cost + queue_cost

        logger.info("%s accepted the order with cost %s and time %s", agent, total_cost, total_time)
        logger.debug("suggested path %s", path)

        with self._lock:
            self._order_applications[agent] = {
                "path": path,
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

        # select best agent
        with self._lock:
            agent = None
            cost = 0.0
            eta = 0.0
            path = None
            for key, value in self._order_applications.items():
                c = self.order_cost_function(value["cost"], value["time"])
                if agent is None or c < cost:
                    agent = key
                    cost = value["cost"]
                    eta = value["time"]
                    path = value["path"]

            if agent is None:
                self.loop_select()  # selet next agent
                return None

            # delete selected order from list
            del self._order_applications[agent]

        logger.info(
            "Agent %s selected with cost %s and eta %s",
            agent,
            cost,
            eta,
        )

        # we have requested the best path, but there is a race-condition
        # which is not checked - a different order might be assigned to one
        # of the agents or one somewhere in the loop might have an error or
        # be back in production. we apply to the "previous" best solution,
        # which might have changed within the timeframe of the application.
        # This could be prevented with locks, but never solved because there
        # might be a unplaned downtime at some point. Thus this problem
        # is not deterministic.

        error = False
        eta = 0.0
        cost = 0.0
        number = 0
        for agent, steps in path:
            try:
                logger.debug("calling assign from OrderNegotiateStub on %s", agent)
                with self._channel(agent) as channel:
                    # numbering steps
                    for step in steps:
                        number += 1
                        step.number = number
                        self._order_steps[number] = step

                    request = market_pb2.OrderInfo(order=self._iams.agent, eta=eta, steps=steps)
                    stub = market_pb2_grpc.OrderNegotiateStub(channel)
                    response = stub.assign(request, timeout=20)

                    eta += response.production_time + response.queue_time + response.transport_time
                    cost += response.production_cost + response.queue_cost + response.transport_cost
            except grpc.RpcError as e:
                logger.debug("[%s] %s: %s", agent, e.code(), e.details())
                error = True
                break

        # cancel order if an error occured
        if error:
            for agent, steps in path:
                request = market_pb2.CancelRequest(order=self._iams.agent)
                try:
                    logger.debug("calling cancel from OrderNegotiateStub on %s", agent)
                    with self._channel(agent) as channel:
                        stub = market_pb2_grpc.OrderNegotiateStub(channel)
                        stub.cancel(request, timeout=20)
                except grpc.RpcError as e:
                    logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            logger.info("Assigned the order with cost %s and time %s", cost, eta)
            self.loop_select()  # selet next agent
            return None
        else:
            logger.info("Assigned the order with cost %s and time %s", cost, eta)
            self._order_state = RootStates.START

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
    def order_update_config(self, retries: int = 0):
        """
        receive order data from service
        """
        pass

    @abstractmethod
    def order_get_data(self):
        """
        return eta and a list of Step instances
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
    def order_start_step(self, step: market_pb2.Step):  # from servicer
        """
        report start execution of a step
        """
        pass

    @abstractmethod
    def order_next_step(self):  # from servicer
        """
        the current agent does not have any steps left and the order should
        connect to the next agent and start the order
        """
        pass

    @abstractmethod
    def order_finish_step(self, step: market_pb2.Step):  # from servicer
        """
        report end execution of a step
        """
        pass


# === EXCECUTION ==============================================================


class OrderNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def apply(self, request: market_pb2.OrderInfo, context) -> market_pb2.OrderOffer:
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
        for step in request.steps:
            response = self.parent.order_validate(request.order or context._agent, step, request.eta)
            if response is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")
            yield response

    @permissions(has_agent=True)
    def assign(self, request: market_pb2.OrderInfo, context) -> market_pb2.OrderCost:
        logger.debug("%s.assign was called by %s", self.__class__.__qualname__, context._agent)

        # manipulate response with step costs
        production_cost = 0.0
        production_time = 0.0
        queue_cost = 0.0
        queue_time = 0.0
        transport_cost = 0.0
        transport_time = 0.0

        for step in request.steps:
            response = self.parent.order_validate(request.order or context._agent, step, request.eta)
            if response is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")

            production_cost += response.production_cost
            production_time += response.production_time
            queue_cost += response.queue_cost
            queue_time += response.queue_time
            transport_cost += response.transport_cost
            transport_time += response.transport_time

        if self.parent.order_start(request.order or context._agent, request.steps, request.eta):
            return market_pb2.OrderCost(
                production_cost=production_cost,
                production_time=production_time,
                queue_cost=queue_cost,
                queue_time=queue_time,
                transport_cost=transport_cost,
                transport_time=transport_time,
            )
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Error assigning order %s" % (request.order or context._agent))

    @permissions(has_agent=True)
    def cancel(self, request: market_pb2.CancelRequest, context) -> Empty:
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        order = request.order or context._agent
        if self.parent.order_cancel(order):
            return Empty()
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Error cancelling order %s" % order)


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

    def _order_start_step(self, order, step):
        """
        """
        try:
            with self._channel(order) as channel:
                stub = market_pb2.OrderCallback(channel)
                logger.debug("Calling OrderCallback.start_step on %s", order)
                stub.start_step(step, timeout=5)
                return True

        except grpc.RpcError as e:
            logger.debug("%s: %s - %s", order, e.code(), e.details())
            return False

    def _order_finish_step(self, order, step):
        """
        """
        try:
            with self._channel(order) as channel:
                stub = market_pb2.OrderCallback(channel)
                logger.debug("Calling OrderCallback.finish_step on %s", order)
                stub.finish_step(step, timeout=5)
                return True

        except grpc.RpcError as e:
            logger.debug("%s: %s - %s", order, e.code(), e.details())
            return False

    @abstractmethod
    def order_validate(self, order: str, step: market_pb2.Step, eta: float) -> market_pb2.OrderCost:
        """
        Called from servicer when the step of an order needs to be evaluated
        retuns market_pb2.OrderCost or None if the request is not valid
        """
        pass

    @abstractmethod
    def order_start(self, order: str, steps: market_pb2.Step, eta: float) -> bool:  # from servicer
        """
        """
        pass

    @abstractmethod
    def order_cancel(self, order: str) -> bool:  # from servicer
        """
        """
        pass


# TODO: implement a scheduler with order_start and order_cancel


# === INTERMEDIATE ============================================================


class IntermediateNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):

    def __init__(self, parent):
        self.parent = parent

    # TODO
    @permissions(has_agent=True)
    def apply(self, request, context):
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)

        self.applications = {}
        order = request.order or context._agent
        eta = request.eta
        response = market_pb2.OrderCost()

        for steps, agents in self.parent.order_split(request.steps):

            # steps is not allowed to be empty
            if steps is None:
                logger.info("Split did not work")
                context.abort(grpc.StatusCode.NOT_FOUND, "Split not possible")

            # if no agent is specifies, this instance wants to add a step
            if agents is None:
                for step in steps:
                    response = self.parent.order_validate(order, step, eta)
                    if response is None:
                        context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")
                    eta += response.production_time + response.queue_time + response.transport_time
                    yield response
                continue

            futures = []
            request = market_pb2.OrderRequest(order=order, steps=steps, eta=eta)
            for agent in agents:
                logger.debug("Adding %s to queue", agent)
                futures.append(self._executor.submit(
                    self.add_application,
                    agent,
                    request,
                    eta,
                ))
            concurrent.futures.wait(futures)

            if not self.applications:
                logger.info("No agent responded")
                context.abort(grpc.StatusCode.NOT_FOUND, "No agent responed")

            # select best agent
            with self._lock:
                agent = None
                agent_responses = None
                cheapest = 0.0

                for key, data in self.applications.items():
                    responses, cost, time = data

                    value = self.parent.order_cost_function(cost, time)
                    if agent is None or value < cheapest:
                        cheapest = value
                        agent = key
                        agent_responses = responses

            for response in agent_responses:
                yield response

    @permissions(has_agent=True)
    def assign(self, request, context):
        logger.debug("%s.assign was called by %s", self.__class__.__qualname__, context._agent)

        # manipulate response with step costs
        production_cost = 0.0
        production_time = 0.0
        queue_cost = 0.0
        queue_time = 0.0
        transport_cost = 0.0
        transport_time = 0.0

        for step in request.steps:
            response = self.parent.order_validate(request.order or context._agent, step, request.eta)
            if response is None:
                context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")

            production_cost += response.production_cost
            production_time += response.production_time
            queue_cost += response.queue_cost
            queue_time += response.queue_time
            transport_cost += response.transport_cost
            transport_time += response.transport_time

        if self.parent.order_start(request.order or context._agent, request.steps, request.eta):
            return market_pb2.OrderCost(
                production_cost=production_cost,
                production_time=production_time,
                queue_cost=queue_cost,
                queue_time=queue_time,
                transport_cost=transport_cost,
                transport_time=transport_time,
            )
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Error assigning order %s" % (request.order or context._agent))

    def add_application(self, agent, request, eta):
        responses = []
        time = 0.0
        cost = 0.0
        try:
            with self._channel(agent) as channel:
                stub = market_pb2.OrderRequest(channel)
                logger.debug("Calling OrderRequest.assign on %s", agent)
                for response in stub.assign(request, timeout=5):
                    time += response.production_time + response.queue_time + response.transport_time
                    cost += response.production_cost + response.queue_cost + response.transport_cost
                    responses.append(response)

        except grpc.RpcError as e:
            logger.debug("%s: %s - %s", agent, e.code(), e.details())
            return None

        logger.debug("Adding %s to applications", agent)
        with self._lock:
            self._applications[agent] = (responses, cost, time)

    @permissions(has_agent=True)
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        order = request.order or context._agent
        if self.parent.order_cancel(order):
            return Empty()
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Error cancelling order %s" % order)


class IntermediateInterface(ABC):
    """
    Splits the steps by ability and connects to different agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orders = {}

    def _grpc_setup(self):
        super()._grpc_setup()
        self._grpc.add(
            market_pb2_grpc.add_OrderNegotiateServicer_to_server,
            IntermediateNegotiateServicer(self),
        )

    @abstractmethod
    def order_validate(self, order, step, eta):
        """
        """
        pass

    @abstractmethod
    def order_split(self, steps):
        """
        iterator, which yields a list of steps and agents. the steps are then passend to
        the agents and one agent is selected, who executes the order. If None is returns
        for agents, this agent instance is used instead.
        """
        pass

    @abstractmethod
    def order_cost_function(self, cost, time):
        """
        returns the costs
        """
        pass

    @abstractmethod
    def order_start(self, order, steps, eta):
        """
        returns the costs
        """
        pass

    @abstractmethod
    def order_cancel(self, order):
        """
        returns the costs
        """
        pass

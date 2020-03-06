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

from .mixins import TopologyMixin
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

                    path.append((response.agent or agent, response.info))
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
        logger.debug("%s suggested path %s", path)

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
            del self._applications[agent]

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
        for agent, steps in path:
            try:
                logger.debug("calling assign from OrderNegotiateStub on %s", agent)
                with self._channel(agent) as channel:
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
        return an instance of OrderInfo
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
        self.topology = None

    @permissions(has_agent=True)
    def apply(self, request, context):
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
        return self.apply_or_assign(request, context)

    @permissions(has_agent=True)
    def assign(self, request, context):
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
        return self.apply_or_assign(request, context, True)

    def apply_or_assign(self, request, context, assign=False):
        self.applications = {}
        order = request.order or context._agent
        eta = request.eta
        previous = None
        response = market_pb2.OrderCosts()

        # split steps
        for steps, labels in self.parent.order_split(request.steps):

            if steps is None or labels is None:
                logger.info("Split did not work")
                context.abort(grpc.StatusCode.NOT_FOUND, "Split not possible")

            # get a list of agents
            agents = []
            for label in labels:
                for agent in self._iams.get_agents(labels):
                    agents.append(agent.name)

            request = market_pb2.OrderRequest(order=order, steps=steps, eta=eta)

            futures = []
            # get all agents via label
            for agent in agents:
                logger.debug("Adding %s to queue", agent)
                futures.append(self._executor.submit(
                    self.add_application,
                    agent.name,
                    previous,
                    request,
                    eta,
                    False,
                ))
            concurrent.futures.wait(futures)

            if not self.applications:
                logger.info("No agent responded")
                context.abort(grpc.StatusCode.NOT_FOUND, "No agent responed")

            # select best agent
            with self._lock:
                agent = None
                agent_response = None
                cost = 0.0

                for key, r in self.applications.items():
                    value = self.parent.order_cost_function(r["response"], eta)
                    if agent is None or value < cost:
                        agent = key
                        agent_response = r["response"]

            # manipulate response with step costs
            response.production_cost += agent_response.production_cost
            response.production_time += agent_response.production_time
            response.queue_time += agent_response.queue_time
            response.transport_cost += agent_response.transport_cost
            response.transport_time += agent_response.transport_time

            # update own virtual state, for example the position of a carrier
            previous = agent
            eta += agent_response.production_time + agent_response.queue_time + agent_response.transport_time

            # if the requst only applied for production, we can resond here
            if not assign:
                continue

            # cancel order on all other agents
            with self._lock:
                for key in self.applications.keys():
                    if key == agent:
                        continue
                    futures.append(self._executor.submit(self.cancel_application, key, order))
        return response

    def add_application(self, agent, previous, request, eta, start):
        try:
            with self._channel(agent) as channel:
                stub = market_pb2.OrderRequest(channel)
                if start:
                    logger.debug("Calling OrderRequest.assign on %s", agent)
                    response = stub.assign(request, timeout=5)

                else:
                    logger.debug("Calling OrderRequest.apply on %s", agent)
                    response = stub.apply(request, timeout=5)

        except grpc.RpcError as e:
            logger.debug("%s: %s - %s", agent, e.code(), e.details())
            return None

        # calculte costs of state change (i.e. transportation costs)
        try:
            # TODO
            weights = self.parent._topology_path(previous, agent, eta)
        except ValueError:
            logger.info("Could not find a valid path from %s to %s", previous, agent)
            return None
        costs, duration = self.parent.order_topology_cost(weights)
        response.transport_cost += costs
        response.transport_time += duration
        response.queue_time = self.parent.order_queue_time(eta, duration)

        logger.debug("Adding %s to applications", agent)
        with self._lock:
            self._applications[agent] = response

    def cancel_application(self, agent, order):
        try:
            with self._channel(agent) as channel:
                stub = market_pb2.OrderRequest(channel)
                logger.debug("Calling OrderRequest.cancel on %s", agent)
                return stub.cancel(market_pb2.CancelRequest, timeout=5)

        except grpc.RpcError as e:
            logger.debug("%s: %s - %s", agent, e.code(), e.details())
            return None

    @permissions(has_agent=True)
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        # TODO
        return super().cancel(request, context)


class ProxyCallbackServicer(market_pb2_grpc.OrderCallbackServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def cancel(self, request, context):
        logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
        # TODO
        return super().cancel(request, context)

    @permissions(has_agent=True)
    def start_step(self, request, context):
        logger.debug("%s.start_step was called by %s", self.__class__.__qualname__, context._agent)
        # TODO
        return super().start_step(request, context)

    @permissions(has_agent=True)
    def finish_step(self, request, context):
        logger.debug("%s.finish_step was called by %s", self.__class__.__qualname__, context._agent)
        # TODO
        return super().finish_step(request, context)


class IntermediateInterface(TopologyMixin, ABC):
    """
    Splits the steps by ability and connects to different agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orders = {}
        self._topology_children = []

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
    def order_split(self, steps):
        """
        iterator, which yields a list of steps and labels. the labels are used to select other
        agents and the steps are the steps which are passed to the agents
        """
        pass

    @abstractmethod
    def order_cost_function(self, response, time):
        """
        returns the costs
        """
        pass

    @abstractmethod
    def order_topology_cost(self, weights):
        """
        calculate the cost and times for state changes (i.e. transportation costs)
        from the weights of the topology path
        """
        pass

    @abstractmethod
    def order_queue_time(self, eta, duration):
        """
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

        # TODO response format is not "good"
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

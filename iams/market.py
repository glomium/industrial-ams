#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import concurrent
import logging

from abc import ABC
from abc import abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from enum import auto
from enum import Enum
from queue import Empty as QueueEmpty
from queue import PriorityQueue

import grpc

from google.protobuf.empty_pb2 import Empty

from iams.utils.auth import permissions

from .mixins import ArangoDBMixin
from .proto import market_pb2
from .proto import market_pb2_grpc


logger = logging.getLogger(__name__)


@dataclass(order=True)
class StepQueue:
    cost: float
    time: float
    step: int
    agent: str
    steps: list = field(default_factory=list, compare=False)


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
    def finish_step(self, request, context) -> Empty:
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
    def start_step(self, request, context) -> Empty:
        logger.debug("%s.start_step was called by %s", self.__class__.__qualname__, context._agent)
        if self.parent._order_state != RootStates.RUNNING:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")

        if self.parent.order_start_step(request):
            return Empty()
        else:
            context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")


class RootInterface(ArangoDBMixin, ABC):
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
                if self._iams.simulation:
                    # shedule shutdown of agent in 60 seconds to avoid
                    # interference with wait in loop_select
                    self._simulation.schedule(60, '_loop')
                else:
                    self.order_finished()
                self._order_state = RootStates.SHUTDOWN

            elif self._order_state == RootStates.CANCEL:
                if self._iams.simulation:
                    # shedule shutdown of agent in 60 seconds to avoid
                    # interference with wait in loop_select
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
        queue = PriorityQueue()
        eta, steps = self.order_get_data()

        if len(steps) == 0:
            logger.error("Shutdown - order %s does not contain steps", self)
            self._order_state = RootStates.SHUTDOWN
            if self._iams.simulation:
                self._simulation.schedule(0, '_loop')
            return None

        futures = set()
        # calculate cost and time estimates from each agent
        # start from first step and select all agents with matching abilities
        query = 'WITH logical FOR a IN agent FILTER @abilities ALL IN a.abilities RETURN a._key'
        for agent in self._arango.aql.execute(query, bind_vars={"abilities": steps[0].abilities}):
            # get production duration, queue time and costs from agent
            futures.add(self._executor.submit(self._order_add_production, queue, agent, steps[0], eta, None))
        concurrent.futures.wait(futures)

        try:
            for item in queue.get(block=False):
                if item.step == len(steps):
                    logger.info("Found optimal production: %s", item)
                    del queue
                    break
                self._order_findall(queue, item, steps[item.step], eta)

        except QueueEmpty:
            logger.info("Retry in 60s - can not build order %s", self)
            self._order_state = RootStates.SHUTDOWN
            # TODO
            # if self._iams.simulation:
            #     self._simulation.schedule(60, '_loop_apply')
            # else:
            #     self._loop_event.wait(60)

        # TODO OLD ========================
        self._order_add_production.cache_clear()

        # get a list of agents
        futures = []
        agents = []
        for labels in self.order_agent_labels():
            for agent in self._iams.get_agents(labels):
                agents.append(agent.name)

        self._order_applications = {}

        # build execution graph

        # get earliest execution time and lengths
        # build "path"
        # schedule either in reverse order (eta large enough) or with earliest execution time

        # get abilities for last step
        for agent in agents:
            futures.append(self._executor.submit(self._order_application, agent, steps, eta))
        concurrent.futures.wait(futures)

        self._order_state = RootStates.SELECT
        self.loop_select()

    def _order_add_production(self, queue, agent, step, eta, item, futures=[]):
        cost = 0.0
        time = 0.0
        if item is None:
            item = StepQueue()

        steps = item.steps

        try:
            logger.debug("calling apply from OrderNegotiateStub on %s", agent)

            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderNegotiateStub(channel)
                request = market_pb2.StepInfo(
                    order=self._iams.agent,
                    time_start=item.time,
                    time_finish=eta,
                    data=step,
                )
                for response in stub.apply(request, timeout=10):
                    if not response.cost:
                        logger.critical("Response from %s is missing cost attribute", agent)
                        return None

                    if not response.step:
                        if self.order_skip_step(step):
                            logger.debug("%s is skipping a step", agent)
                            item.step += 1
                            queue.put(item)
                            return None
                        logger.info("Response from %s is missing step attribute", agent)

                    steps.append(response.step)
                    cost += response.cost.production_cost + response.cost.transport_cost + response.cost.queue_cost
                    time += response.cost.production_time + response.cost.transport_time + response.cost.queue_time

        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return None

        if item.time > eta:
            logger.debug("Cannot product order in time - abort")
            return None

        logger.info("%s accepted the step with cost %s and duration %s", agent, cost, time)
        item.steps = steps
        item.cost += cost
        item.time += time
        item.step += 1

        queue.put(item)

    def _order_findall(self, queue, item, step, eta):
        # select all agents which are reachable from the previous steps
        query = 'WITH logical FOR target IN agent FILTER @abilities ALL IN target.abilities '
        'FOR v, e IN OUTBOUND SHORTEST_PATH @agent TO target GRAPH \'connections\' '
        'RETURN {key: v._key, init: e == null, reached: target==v}'

        # The query returns every shortest path to every reachable target-agent
        # As we get overlap between paths we can order all paths to minmize the calls to agents
        # this is done on the fly by this algorithm
        paths = []
        for current in self._arango.aql.execute(query, bind_vars={"abilities": step.abilities, "agent": item.agent}):
            if current["init"]:
                if current["reached"]:
                    paths.append((current["key"], []))
                    continue
                path = [None]
            path.append(current["key"])
            if current["reached"]:
                paths.append((current["key"], path))
                continue

        findall_futures = set()
        cache = {}
        for agent, path in paths:
            # collect futures for transport
            if len(path) > 2:
                for x in range(1, len(path) - 1):
                    previous, current, target = path[x - 1:x + 2]
                    futures = [cache[key] for key in path[2:x + 1]]
                    if target not in cache:
                        cache[target] = self._executor.submit(
                            self._order_cost_transport, previous, current, target, futures,
                        )
                futures.append(cache[target])
            else:
                futures = []

            findall_futures.add(self._executor.submit(
                self._order_add_production, queue, agent, step, eta, deepcopy(item), futures,
            ))
        concurrent.futures.wait(findall_futures)

    def _order_cost_transport(self, previous, current, target, futures):
        return 0.0, 0.0

    def _order_application(self, agent, step, eta):
        """
        this runs in a seperate thread. it connects to an agent and adds its price and cost
        to the _order_applications dictionary
        """
        cost = 0.0
        time = 0.0

        # ask agent to execute last step

        # select agents starting from last and ask them if they can produce the product

        # select the cheapest execution

        normal = False
        path = []
        steps = []

        # we sort the steps from last to first and calculate the eta backwards.
        # thus we can implement least time and least cost algorithms
        # (when eta is negative or small, the costs might be neglectable and
        # for high eta we optimise the production cost)

        try:
            logger.debug("calling apply from OrderNegotiateStub on %s", agent)
            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderNegotiateStub(channel)

                # ask agents to execute steps in reverse in time decreasing order
                for step in steps[::-1]:

                    # we can't start the order in the past
                    if eta <= 0.0:
                        path = []
                        cost = 0.0
                        time = 0.0
                        normal = True
                        break

                    request = market_pb2.StepInfo(
                        order=self._iams.agent,
                        time_finish=eta,
                        data=step,
                    )
                    for response in stub.apply(request, timeout=10):
                        if not response.cost:
                            logger.critical("Response from %s is missing cost attribute", agent)
                            return None

                        if not response.step:
                            if self.order_skip_step(step):
                                logger.debug("%s is skipping a step", agent)
                                continue
                            logger.critical("Response from %s is missing step attribute", agent)

                        path.append((response.agent or agent, response.step))
                        cost += response.cost.production_cost + response.cost.transport_cost + response.cost.queue_cost
                        eta -= response.cost.production_time + response.cost.transport_time + response.cost.queue_time
                        time += response.cost.production_time + response.cost.transport_time + response.cost.queue_time

                # ask agents to execute steps in time increasing order
                for step in steps:

                    # the reverse scheduling worked, thus we dont need to do anything here
                    if not normal:
                        break

                    request = market_pb2.StepInfo(
                        order=self._iams.agent,
                        time_start=time,
                        data=step,
                    )
                    for response in stub.apply(request, timeout=10):
                        if not response.cost:
                            logger.critical("Response from %s is missing cost attribute", agent)
                            return None

                        if not response.step:
                            if self.order_skip_step(step):
                                logger.debug("%s is skipping a step", agent)
                                continue
                            logger.critical("Response from %s is missing step attribute", agent)

                        path.append((response.agent or agent, response.step))
                        cost += response.cost.production_cost + response.cost.transport_cost + response.cost.queue_cost  # noqa
                        time += response.cost.production_time + response.cost.transport_time + response.cost.queue_time

        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return None

        logger.info("%s accepted the order with cost %s, eta %s and duration %s", agent, cost, eta, time)
        logger.debug("suggested path %s", path)

        with self._lock:
            self._order_applications[agent] = {
                "path": path,
                "cost": cost,
                "time": time,
                "start": eta,
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
                c = self.order_cost_function(value["cost"], value["time"], value["start"])
                if agent is None or c < cost:
                    agent = key
                    cost = value["cost"]
                    path = value["path"]

            if agent is None:
                self.loop_select()  # selet next agent
                return None

            # delete selected order from list
            del self._order_applications[agent]

        logger.info(
            "Agent %s selected with cost %s",
            agent,
            cost,
        )

        # we have requested the best path, but there is a race-condition
        # which is not checked - a different order might be assigned to one
        # of the agents or one somewhere in the loop might have an error or
        # be back in production. we apply to the "previous" best solution,
        # which might have changed within the timeframe of the application.
        # This could be prevented with locks, but never solved because there
        # might be a unplaned downtime at some point. Thus this problem
        # is not deterministic.

        # previous = None
        # aggregated = []
        # for agent, step in path:
        #     steps = []

        error = False
        eta = 0.0
        cost = 0.0
        number = 0
        for agent, step in path:
            try:
                logger.debug("calling assign from OrderNegotiateStub on %s", agent)
                with self._channel(agent) as channel:
                    # numbering steps
                    number += 1
                    step.order = self._iams.agent
                    step.number = number
                    step.time_start = eta
                    self._order_steps[number] = step

                    stub = market_pb2_grpc.OrderNegotiateStub(channel)
                    response = stub.assign(step, timeout=10)

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

    def order_cost_function(self, value: float, time: float, start: float):
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
        return due date (eta) and a tree (list) of step instances.

        One Step
        [
            1,
            2,
        ]

        find best execution place for 1, then find best execution for 2

        linear (list) -> TODO: Not implemented
        [
            [1,2,3],
            4
        ]

        find best execution for [1,2,3], then find best execution for 4

        parallel (set) -> TODO: Not Implemented!
        [
            {[1, 2], 3},
            4,
        ]

        Schedule [1,2] and 3, if [1,2] and 3 is finished schedule 4

        multipath -> TODO: Not Implemented!
        [
            {"a":1,"b":2,"c":3},
            4,
        ]

        Find best between a, b and c and schedule one, then schedule 4

        combined -> TODO: Not Implemented!
        [
            [1,2]
            {"a":[3,4],"b":5,"c":{6,[7,8]}},
            9,
        ]
        """
        pass

    @abstractmethod
    def order_agent_labels(self):
        """
        iterator, which generates a list of labels which is used to filter docker
        services for devices which can execute the last step of this order

        this is used to specify an initial condition for the betting algorithm
        to increase the search space.
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
    def order_skip_step(self, step):  # called from servicer
        """
        report start execution of a step
        """
        pass

    @abstractmethod
    def order_start_step(self, step):  # from servicer
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
    def order_finish_step(self, step):  # from servicer
        """
        report end execution of a step
        """
        pass


# === EXCECUTION ==============================================================


class OrderNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):

    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def apply(self, request, context) -> market_pb2.OrderOffer:
        logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
        response = self.parent.order_validate(
            request.order or context._agent,
            request.data, request.time_start, request.time_finish,
        )
        if response is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")
        yield response

    # TODO
    @permissions(has_agent=True)
    def assign(self, request, context) -> market_pb2.OrderCost:
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
    def order_validate(self, order: str, step, start: float, finish: float) -> market_pb2.OrderCost:
        """
        Called from servicer when the step of an order needs to be evaluated
        retuns market_pb2.OrderCost or None if the request is not valid
        """
        pass

    @abstractmethod
    def order_start(self, order: str, steps, eta: float) -> bool:  # from servicer
        """
        """
        pass

    @abstractmethod
    def order_cancel(self, order: str) -> bool:  # from servicer
        """
        """
        pass


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

    # TODO
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


# === SCHEDULER ===============================================================


# TODO: implement a scheduler with order_start and order_cancel

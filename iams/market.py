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
    WAIT = auto()  # order apply failed and is waiting to re-request
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

            elif self._order_state == RootStates.WAIT:
                if not self._iams.simulation:
                    self._loop_event.wait(60)

            elif self._order_state == RootStates.START:
                if not self._iams.simulation:
                    self.order_started()
                self._order_state = RootStates.RUNNING

            elif self._order_state == RootStates.RUNNING:
                self.loop_running()

            elif self._order_state == RootStates.FINISH:
                if not self._iams.simulation:
                    self.order_finished()
                self._order_state = RootStates.SHUTDOWN

            elif self._order_state == RootStates.CANCEL:
                if not self._iams.simulation:
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
                    if self._order_select(item):
                        break
                self._order_findall(queue, item, steps[item.step], eta)
                queue.task_done()
        except QueueEmpty:
            logger.info("Retry in 60s - can not build order %s", self)
            self.loop_wait()
            return None

        del queue
        self._order_state = RootStates.START
        self.loop_start()

    def loop_wait(self):
        if self._iams.simulation:
            self._simulation.schedule(60, '_loop_apply')
        else:
            self._order_state == RootStates.WAIT

    # TODO
    def _order_select(self, item):
        """
        iterates over the information stored in item and schedules the order steps on the agents
        """
        pass

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
            logger.debug("Cannot produce order in time - abort")
            return None

        logger.info("%s accepted the step with cost %s and duration %s", agent, cost, time)
        item.steps = steps
        item.cost += cost
        item.time += time
        item.step += 1

        queue.put(item)

    def _order_findall(self, queue, item, step, eta):
        # select all agents which are reachable from the previous steps
        query = '''WITH logical FOR target IN agent FILTER @abilities ALL IN target.abilities
        FOR v, e IN OUTBOUND SHORTEST_PATH @agent TO target GRAPH 'connections'
        RETURN {key: v._key, init: e == null, reached: target==v}'''

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

    # TODO
    def _order_cost_transport(self, previous, current, target, futures):
        return 1.0, 1.0

    def loop_running(self):
        """
        """
        if self._iams.simulation is False:
            logger.debug("waiting for event")
            self._loop_event.wait()

    @abstractmethod
    def order_update_config(self, retries: int=0):
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


# === SCHEDULER ===============================================================


# TODO: implement a scheduler with order_start and order_cancel

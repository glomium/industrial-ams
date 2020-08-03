#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import concurrent.futures
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

# from google.protobuf.empty_pb2 import Empty

from iams.utils.auth import permissions

from .mixins import ArangoDBMixin
from .mixins import TopologyMixin
from .proto import market_pb2
from .proto import market_pb2_grpc
from .proto.market_pb2 import Step


logger = logging.getLogger(__name__)


@dataclass(order=True)
class StepQueue:
    cost: float
    time: float
    step: int
    agent: str = field(compare=False, repr=False, default=None)
    steps: list = field(default_factory=list, compare=False, repr=False)
    # interface: str = field(compare=False, repr=False, default=None)


class OrderStates(Enum):
    APPLY = auto()  # order is applying to agents
    WAIT = auto()  # order apply failed and is waiting to re-request
    START = auto()  # Callback function
    RUNNING = auto()  # Order is currently executed
    FINISH = auto()  # Callback function
    REASSIGN = auto()  # Callback function
    CANCEL = auto()  # Callback function
    SHUTDOWN = auto()  # order agent is waiting to be killed by docker


class OrderServicer(market_pb2_grpc.OrderServicer):
    def __init__(self, parent):
        self.parent = parent


class OrderWorkerServicer(market_pb2_grpc.OrderWorkerServicer):
    def __init__(self, parent):
        self.parent = parent

    @permissions(has_agent=True)
    def transport_assign(self, request, context):
        logger.debug("%s.transport_assign was called by %s", self.__class__.__qualname__, context._agent)
        logger.debug("transport_assign request: %s", request)
        return request

    @permissions(has_agent=True)
    def transport_offer(self, request, context):
        logger.debug("%s.transport_offer was called by %s", self.__class__.__qualname__, context._agent)
        request.cost += 5.0
        return request

    @permissions(has_agent=True)
    def production_assign(self, request, context):
        logger.debug("%s.production_assign was called by %s", self.__class__.__qualname__, context._agent)
        request.cost += 1.0
        return request

    @permissions(has_agent=True)
    def production_offer(self, request, context):
        logger.debug("%s.production_offer was called by %s", self.__class__.__qualname__, context._agent)
        request.cost += 1.0
        return request


class MarketInterface(ArangoDBMixin, ABC):
    """
    Has the steps, asks agents to produce the steps and tracks the process
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._order_state = OrderStates.APPLY
        self._order_applications = {}
        self._order_steps = {}

    def _grpc_setup(self):
        super()._grpc_setup()
        self._grpc.add(
            market_pb2_grpc.add_OrderServicer_to_server,
            OrderServicer(self),
        )

    def setup(self):
        config = self.market_update_config(10)
        if config is not None:
            logger.debug("%s._config is overwritten with config from service", self.__class__.__qualname__)
            self._config = config

    def simulation_start(self):
        logger.debug("Simulation start called")
        self.loop_apply()

    def _loop(self):
        while not self._stop_event.is_set():
            logger.debug("Running loop from state %s", self._order_state)

            if self._order_state == OrderStates.APPLY:
                self.loop_apply()

            elif self._order_state == OrderStates.WAIT:
                if not self._iams.simulation:
                    self._loop_event.wait(60)
                    # self._order_state == OrderStates.APPLY

            elif self._order_state == OrderStates.START:
                if not self._iams.simulation:
                    self.order_started()
                self._order_state = OrderStates.RUNNING

            elif self._order_state == OrderStates.RUNNING:
                self.loop_running()

            elif self._order_state == OrderStates.FINISH:
                if not self._iams.simulation:
                    self.order_finished()
                self._order_state = OrderStates.SHUTDOWN

            elif self._order_state == OrderStates.CANCEL:
                if not self._iams.simulation:
                    self.order_canceled()
                self._order_state = OrderStates.SHUTDOWN

            elif self._order_state == OrderStates.REASSIGN:
                if not self._iams.simulation:
                    self.order_reassigned()
                self._order_state = OrderStates.APPLY

            elif self._order_state == OrderStates.SHUTDOWN:
                self._iams.call_destroy()
                logger.debug("Waiting for the shutdown signal from docker")
                self._stop_event.wait(30)

            if self._iams.simulation is False:
                self._loop_event.clear()

    def loop_apply(self):
        """
        """
        logger.debug("running loop_apply")

        eta, steps = self.market_get_order()
        try:
            item = self._market_get_order(eta, steps)
        except RuntimeError:
            logger.exception("Shutdown - order %s does not contain steps", self)
            self._order_state = OrderStates.SHUTDOWN
            if self._iams.simulation:
                self._simulation.schedule(0, '_loop')
            return None

        if item is None:
            logger.info("Retry in 60s - can not build order %s", self)
            self.loop_wait()
            return None

        self._order_state = OrderStates.START

    def loop_wait(self):
        if self._iams.simulation:
            self._simulation.schedule(60, 'loop_apply')
        else:
            self._order_state == OrderStates.WAIT

    def _market_select(self, item):
        """
        iterates over the information stored in item and schedules the order steps on the agents
        """

        # compress production on the same agent to a single call
        current = None
        merge = {}
        for n, data in enumerate(item.steps):
            agent, step = data
            if isinstance(step, market_pb2.Transport):
                previous = None
            elif isinstance(step, market_pb2.Production):
                if previous == agent:
                    try:
                        merge[current].append(n)
                    except KeyError:
                        merge[current] = [n]
                else:
                    current = n
                previous = agent
            else:
                raise NotImplementedError("Step is not an instance of Transport or Production")

        logger.debug("merging production steps: %s", merge)

        delete = []
        for step, data in merge.items():
            for i in data:
                item.steps[step].steps += item.steps[i].steps
                delete.append(i)
        delete.sort(reverse=True)
        for i in delete:
            del item.steps[i]
        del merge

        # TODO: The assign can be done in reverse so that the schedule take place with
        # respect of an eta
        # item.steps.reverse()
        agents_transport = set()
        agents_production = set()
        try:
            for agent, step in item.steps:
                if isinstance(step, market_pb2.Transport):
                    with self._channel(agent) as channel:
                        stub = market_pb2_grpc.OrderWorkerStub(channel)
                        result = stub.transport_assign(step, timeout=10)
                    agents_transport.add(agent)
                    logger.debug("RESULT: %s", result)
                elif isinstance(step, market_pb2.Production):
                    with self._channel(agent) as channel:
                        stub = market_pb2_grpc.OrderWorkerStub(channel)
                        result = stub.production_assign(step, timeout=10)
                    agents_production.add(agent)
                    logger.debug("RESULT: %s", result)
            return True

        except grpc.RpcError as e:
            logger.info("Order %s could not be started: %s - %s", self._iams.agent, e.code(), e.details())
        except NotImplementedError as e:
            logger.exception(e)

        # abort and cleanup
        for agent in agents_transport:
            # cancel order on agent
            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderWorkerStub(channel)
                stub.transport_cancel(market_pb2.Cancel(order=self._iams.agent), timeout=10)
            agents_transport.remove(agent)

        for agent in agents_production:
            # cancel order on agent
            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderWorkerStub(channel)
                stub.production_cancel(market_pb2.Cancel(order=self._iams.agent), timeout=10)
            agents_production.remove(agent)

        return False

    def _market_cost_transport(self, agent, target, futures):
        if futures:
            concurrent.futures.wait(futures[-1])
            result = futures[-1].result()
            previous_agent = result.current_agent
        else:
            previous_agent = None

        try:
            logger.debug("calling transport_offer from OrderWorkerStub on %s", agent)
            # TODO: this also needs to include information about the transported item
            request = market_pb2.Transport(
                order=self._iams.agent,
                previous_agent=previous_agent,
                current_agent=agent,
                target_agent=target,
            )
            logger.debug("transport at %s from %s to %s", agent, previous_agent, target)

            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderWorkerStub(channel)
                result = stub.transport_offer(request, timeout=10)
                logger.debug("Estimate transport cost from %s to %s: %s", agent, target, result)
                return agent, stub.transport_offer(request, timeout=10)

        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return agent, None

    def _market_cost_production(self, agent, step, item, futures):
        logger.debug("calling %s to estimate production cost", agent)
        assert isinstance(step, market_pb2.Step), "Step %s is not an instance of market_pb2.Step" % step.__class__.__qualname__  # noqa: E501

        # wait for futures to be executed
        done, not_done = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)
        for f in futures:

            # skip if a future is not done with it's execution
            if not f.done():
                continue

            # get the result (or on failure raise the exception)
            transport_agent, result = f.result()

            # skip this path, if the transport is not valid
            if result is None:
                return None

            # add the transport response to the steps
            item.steps.append((transport_agent, result))

            item.cost += result.cost
            item.time += result.time_work + result.time_queue

        try:
            logger.debug("calling production_offer from OrderWorkerStub on %s", agent)
            request = market_pb2.Production(
                order=self._iams.agent,
                steps=[step],
            )

            with self._channel(agent) as channel:
                stub = market_pb2_grpc.OrderWorkerStub(channel)
                result = stub.production_offer(request, timeout=10)

            logger.debug("Estimate production cost from %s: %s", agent, result)

        except grpc.RpcError as e:
            logger.debug("[%s] %s: %s", agent, e.code(), e.details())
            return None

        item.cost += result.cost
        item.time += result.time_work + result.time_queue

        # add the production response to the item, mark the step as finished and return the object
        logger.info("%s accepted the step with cost %s and duration %s", agent, item.cost, item.time)
        item.step += 1
        item.steps.append((agent, result))
        item.agent = agent
        # item.interface = result.steps[-1].interface or None
        return item

    def _market_get_order(self, eta, steps):
        logger.debug("get order costs for steps: %s", steps)
        queue = PriorityQueue()
        position = self._iams.position
        step = self.market_current_step()
        item = StepQueue(cost=0.0, time=0.0, step=step, agent=position)
        self._market_findall(queue, item, steps[step], eta)

        try:
            while True:
                item = queue.get(block=False)
                if item.step == len(steps):
                    if self._market_select(item):
                        logger.info("Found optimal production: %s", item)
                        return item
                    else:
                        logger.info("Order execution was rejected: %s", item)
                else:
                    current_step = steps[item.step]
                    if not isinstance(current_step, Step):
                        raise RuntimeError("Step %s is not an instance of Step", item.step)
                    self._market_findall(queue, item, steps[item.step], eta)
                queue.task_done()

        except QueueEmpty:
            return None

    def _order_get_paths(self, current, abilities):
        logger.debug("looking for all agents with abilities: %s", abilities)
        query = 'WITH logical FOR a IN agent FILTER @abilities ALL IN a.abilities RETURN a._key'
        bind_vars = {"abilities": list(abilities)}
        for agent in self._arango_client.aql.execute(query, bind_vars=bind_vars):
            if current is None:
                yield [agent]
            else:
                logger.debug("looking for paths between %s and %s", current, agent)
                query = '''WITH logical
                FOR p IN OUTBOUND K_SHORTEST_PATHS @current TO @agent GRAPH 'connections'
                RETURN p.vertices[*]._key'''
                # TODO: this searches ALL possible connections, which might lead to some performance issues
                # for larger graphs. The recommendation is to use K_SHORTEST_PATHS only with a LIMIT, which
                # is also dependent on the size of the samples.

                # The query returns every shortest path to every reachable target-agent
                # As we get overlap between paths we can order all paths to minmize the calls to agents
                # this is done on the fly by this algorithm
                bind_vars = {"current": f"agent/{current!s}", "agent": f"agent/{agent!s}"}
                for path in self._arango_client.aql.execute(query, bind_vars=bind_vars):
                    yield path

    def _market_findall(self, queue, item, step, eta):
        logger.debug("findall  %s %s", item, step)

        findall_futures = set()

        for path in self._order_get_paths(item.agent, step.abilities):
            logger.debug("getting costs for path %s", path)
            cache = {}
            futures = []

            # calculate transport costs
            if len(path) == 1:
                target = path[0]
            else:
                for x in range(len(path) - 1):
                    current, target = path[x:x + 2]
                    cached_futures = list([cache[key] for key in path[1:x + 1]])
                    if target not in cache:
                        cache[target] = self._executor.submit(
                            self._market_cost_transport, current, target, cached_futures,
                        )
                        futures.append(cache[target])

            # collect cost for execution
            findall_futures.add(self._executor.submit(
                self._market_cost_production, target, step, deepcopy(item), futures,
            ))

        # wait for futures to be executed then add (valid) results to queue
        done, not_done = concurrent.futures.wait(findall_futures)

        valid = False
        for f in done:
            result = f.result()
            if isinstance(result, StepQueue):

                # check if order can be produced within an eta
                if eta > 0.0 and result.time > eta:
                    logger.info("Cannot produce within given ETA - continue with different path")
                    continue
                logger.debug("adding %s to queue", result)
                queue.put(result)
                valid = True

        # if this step cannot be executed, we're trying ask if it is allowed to be skipped
        if not valid and self.order_skip_step(step):
            logger.info("Skipping step %s, because it cannot be executed", step)
            item.step += 1
            queue.put(item)

    def loop_running(self):
        """
        """
        if self._iams.simulation is False:
            logger.debug("waiting for event")
            self._loop_event.wait()

    def market_current_step(self) -> int:
        """
        returns the current step (integer)
        """
        return 0

    @abstractmethod
    def market_update_config(self, retries: int = 0):
        """
        receive order data from service
        """
        pass

    @abstractmethod
    def market_get_order(self):
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
    def order_reassign(self):  # from servicer
        """
        callback to reassign the order
        """
        pass

    @abstractmethod
    def order_reassigned(self):
        """
        cleanup after order reassign
        """
        pass

    @abstractmethod
    def order_canceled(self):
        """
        cleanup after order cancelling
        """
        pass

    def order_skip_step(self, step):  # called from servicer
        """
        report start execution of a step
        """
        return False

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


class MarketWorkerInterface(TopologyMixin, ABC):
    """
    """

    def _grpc_setup(self):
        super()._grpc_setup()
        self._grpc.add(
            market_pb2_grpc.add_OrderWorkerServicer_to_server,
            OrderWorkerServicer(self),
        )


# class OrderCallbackServicer(market_pb2_grpc.OrderCallbackServicer):
#   def __init__(self, parent):
#       self.parent = parent

#   @permissions(has_agent=True)
#   def cancel(self, request, context):
#       logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
#       if self.parent._order_state != OrderStates.RUNNING:
#           context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")
#       if self.parent.order_cancel():
#           self.parent._order_state = OrderStates.REASSIGN
#           if self._iams.simulation:
#               self._simulation.schedule(0.0, '_loop')
#           else:
#               self.parent._loop_event.set()
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")
#   @permissions(has_agent=True)
#   def finish_step(self, request, context) -> Empty:
#       logger.debug("%s.finish_step was called by %s", self.__class__.__qualname__, context._agent)
#       if self.parent._order_state != OrderStates.RUNNING:
#           context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")
#       if self.parent.order_finish_step(request):
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")
#   @permissions(has_agent=True)
#   def next_step(self, request: Empty, context) -> Empty:
#       logger.debug("%s.next_step was called by %s", self.__class__.__qualname__, context._agent)
#       if self.parent._order_state != OrderStates.RUNNING:
#           context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")
#       if self.parent.order_next_step(request):
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")
#   @permissions(has_agent=True)
#   def reassign(self, request, context):
#       logger.debug("%s.reassign was called by %s", self.__class__.__qualname__, context._agent)
#       if self.parent._order_state != OrderStates.RUNNING:
#           context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")
#       if self.parent.order_reassign():
#           self.parent._order_state = OrderStates.APPLY
#           if self._iams.simulation:
#               self._simulation.schedule(0.0, '_loop')
#           else:
#               self.parent._loop_event.set()
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")
#   @permissions(has_agent=True)
#   def start_step(self, request, context) -> Empty:
#       logger.debug("%s.start_step was called by %s", self.__class__.__qualname__, context._agent)
#       if self.parent._order_state != OrderStates.RUNNING:
#           context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Request does not match state-machine")
#       if self.parent.order_start_step(request):
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.UNAVAILABLE, "Request was aborted")


# class OrderNegotiateServicer(market_pb2_grpc.OrderNegotiateServicer):

#   def __init__(self, parent):
#       self.parent = parent

#   @permissions(has_agent=True)
#   def apply(self, request, context) -> market_pb2.OrderOffer:
#       logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
#       response = self.parent.order_negotiate_validate(
#           request.order or context._agent,
#           request.data, request.time_start, request.time_finish,
#       )
#       if response is None:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")
#       yield response

#   @permissions(has_agent=True)
#   def assign(self, request, context) -> market_pb2.OrderCost:
#       logger.debug("%s.assign was called by %s", self.__class__.__qualname__, context._agent)

#       # manipulate response with step costs
#       production_cost = 0.0
#       production_time = 0.0
#       queue_cost = 0.0
#       queue_time = 0.0
#       transport_cost = 0.0
#       transport_time = 0.0

#       for step in request.steps:
#           response = self.parent.order_negotiate_validate(request.order or context._agent, step, request.eta)
#           if response is None:
#               context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")

#           production_cost += response.production_cost
#           production_time += response.production_time
#           queue_cost += response.queue_cost
#           queue_time += response.queue_time
#           transport_cost += response.transport_cost
#           transport_time += response.transport_time

#       if self.parent.order_start(request.order or context._agent, request.steps, request.eta):
#           return market_pb2.OrderCost(
#               production_cost=production_cost,
#               production_time=production_time,
#               queue_cost=queue_cost,
#               queue_time=queue_time,
#               transport_cost=transport_cost,
#               transport_time=transport_time,
#           )
#       else:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Error assigning order %s" % (request.order or context._agent))

#   @permissions(has_agent=True)
#   def cancel(self, request: market_pb2.CancelRequest, context) -> Empty:
#       logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
#       order = request.order or context._agent
#       if self.parent.order_negotiate_cancel(order):
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Error cancelling order %s" % order)

#   def _order_start_step(self, order, step):
#       """
#       """
#       try:
#           with self._channel(order) as channel:
#               stub = market_pb2.OrderCallback(channel)
#               logger.debug("Calling OrderCallback.start_step on %s", order)
#               stub.start_step(step, timeout=5)
#               return True

#       except grpc.RpcError as e:
#           logger.debug("%s: %s - %s", order, e.code(), e.details())
#           return False

#   def _order_finish_step(self, order, step):
#       """
#       """
#       try:
#           with self._channel(order) as channel:
#               stub = market_pb2.OrderCallback(channel)
#               logger.debug("Calling OrderCallback.finish_step on %s", order)
#               stub.finish_step(step, timeout=5)
#               return True

#       except grpc.RpcError as e:
#           logger.debug("%s: %s - %s", order, e.code(), e.details())
#           return False

# class OrderProductionServicer(market_pb2_grpc.OrderProductionServicer):
#     def __init__(self, parent):
#        self.parent = parent

#   @permissions(has_agent=True)
#   def apply(self, request, context) -> market_pb2.OrderOffer:
#       logger.debug("%s.apply was called by %s", self.__class__.__qualname__, context._agent)
#       response = self.parent.order_transport_validate(
#           request.order or context._agent,
#           request.data, request.time_start, request.time_finish,
#       )
#       if response is None:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")
#       yield response

#   @permissions(has_agent=True)
#   def assign(self, request, context) -> market_pb2.OrderCost:
#       logger.debug("%s.assign was called by %s", self.__class__.__qualname__, context._agent)

#       # manipulate response with step costs
#       production_cost = 0.0
#       production_time = 0.0
#       queue_cost = 0.0
#       queue_time = 0.0
#       transport_cost = 0.0
#       transport_time = 0.0

#       for step in request.steps:
#           response = self.parent.order_transport_validate(request.order or context._agent, step, request.eta)
#           if response is None:
#               context.abort(grpc.StatusCode.NOT_FOUND, "Agent can not provide the services required")

#           production_cost += response.production_cost
#           production_time += response.production_time
#           queue_cost += response.queue_cost
#           queue_time += response.queue_time
#           transport_cost += response.transport_cost
#           transport_time += response.transport_time

#       if self.parent.order_transport_start(request.order or context._agent, request.steps, request.eta):
#           return market_pb2.OrderCost(
#               production_cost=production_cost,
#               production_time=production_time,
#               queue_cost=queue_cost,
#               queue_time=queue_time,
#               transport_cost=transport_cost,
#               transport_time=transport_time,
#           )
#       else:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Error assigning order %s" % (request.order or context._agent))

#   @permissions(has_agent=True)
#   def cancel(self, request: market_pb2.CancelRequest, context) -> Empty:
#       logger.debug("%s.cancel was called by %s", self.__class__.__qualname__, context._agent)
#       order = request.order or context._agent
#       if self.parent.order_transport_cancel(order):
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Error cancelling order %s" % order)

#   @permissions(has_agent=True)
#   def start(self, request: StepInfo, context) -> Empty:
#       logger.debug("%s.startl was called by %s", self.__class__.__qualname__, context._agent)
#       order = request.order or context._agent
#       if self.parent.order_transport_cancel(order):
#           return Empty()
#       else:
#           context.abort(grpc.StatusCode.NOT_FOUND, "Error starting order %s" % order)

#   def _order_start_step(self, order, step):
#       """
#       """
#       try:
#           with self._channel(order) as channel:
#               stub = market_pb2.OrderCallback(channel)
#               logger.debug("Calling OrderCallback.start_step on %s", order)
#               stub.start_step(step, timeout=5)
#               return True

#       except grpc.RpcError as e:
#           logger.debug("%s: %s - %s", order, e.code(), e.details())
#           return False

#   def _order_finish_step(self, order, step):
#       """
#       """
#       try:
#           with self._channel(order) as channel:
#               stub = market_pb2.OrderCallback(channel)
#               logger.debug("Calling OrderCallback.finish_step on %s", order)
#               stub.finish_step(step, timeout=5)
#               return True

#       except grpc.RpcError as e:
#           logger.debug("%s: %s - %s", order, e.code(), e.details())
#           return False

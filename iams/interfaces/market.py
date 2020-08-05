#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

import networkx as nx

from iams.proto import market_pb2


logger = logging.getLogger(__name__)


@dataclass()
class StepGroup:
    steps: list = field(default_factory=list, repr=True, compare=True)
    primary: bool = field(default=False, compare=False)
    group: str = field(default=None, compare=False)

    def __hash__(self):
        return hash(self.steps[0])


@dataclass(order=["name"], unsafe_hash=True)
class AppNode:
    name: str = field(hash=True)
    agent: str = field(hash=True, default=None)
    interface: str = field(hash=True, default=None)
    transport: bool = field(hash=True, default=False)
    terminal: bool = field(hash=True, default=False)

    # def __str__(self):
    #     if self.terminal:
    #         return self.name
    #     elif self.transport:
    #         return '%s:%s:%s' % (self.name, self.agent, self.interface)
    #     else:
    #         return '%s:%s@%s' % (self.name, self.agent, self.interface)


class OrderInterface(ABC):

    def __init__(self, name, config=None, steps=[]):
        self.instance = market_pb2.Order(identifier=name)
        if config:
            self.load(config)
        else:
            for step in steps:
                self.instance.steps.append(step)

        # load steps to graph
        steps = set()
        self.production_steps = nx.DiGraph()
        for step in self.instance.steps:

            if not step.name:
                raise ValueError("Name of step needs to be set")
            steps.add(step.name)

            self.production_steps.add_node(step.name, group=step.group or None, primary=step.primary)
            for edge in step.edges:
                self.production_steps.add_edge(step.name, edge)

        if len(steps) != len(self.production_steps):
            raise IndexError("Edges %s are not specified" % set(self.production_steps.nodes).difference(steps))

        # group production
        self.production_groups = self.group_production(self.production_steps)

        self.application_finish()
        # self.update_nodes_cache()

    @classmethod
    def group_production(cls, steps):
        assert nx.is_directed_acyclic_graph(steps), "Steps need to be a directed acyclic graph"
        g = nx.DiGraph()

        first = set()
        last = set()
        for name in steps.nodes.keys():
            if sum([1 for x in steps.predecessors(name)]) == 0:
                first.add(name)
            if sum([1 for x in steps.successors(name)]) == 0:
                last.add(name)

        assert first, "Graph does not contain any data"

        # if we only have one group we're done here
        if first == last:
            g.add_node(StepGroup(sorted(first), primary=True))
            return g

        # validate that there is one primary starting group
        if len(first) > 1:
            primary = defaultdict(list)
            groups = defaultdict(list)
            for name in first:
                if steps.nodes[name].get('primary', False):
                    primary[steps.nodes[name].get('group', None)].append(name)
                groups[steps.nodes[name].get('group', None)].append(name)
            if len(primary) > 0:
                groups = primary
            assert len(groups) == 1, "Need exactly one primary starting group"
            if None in groups:
                assert len(groups[None]) == 1, "Need exactly one primary starting node"
            start_group_name, start = groups.popitem()
            start = set(start)
        else:
            start_group_name = None
            start = first

        # validate that there is one primary finishing group
        if len(last) > 1:
            primary = defaultdict(list)
            groups = defaultdict(list)
            for name in last:
                if steps.nodes[name].get('primary', False):
                    primary[steps.nodes[name].get('group', None)].append(name)
                groups[steps.nodes[name].get('group', None)].append(name)

            if len(primary) > 0:
                groups = primary
            assert len(groups) == 1, "Need exactly one primary starting group"
            if None in groups:
                assert len(groups[None]) == 1, "Need exactly one primary starting node"
            finish_group_name, finish = groups.popitem()
            finish = set(finish)
        else:
            finish_group_name = None
            finish = last

        # Look if there is a path between primary inital and final nodes
        path = False
        for i in start:  # pragma: no branch
            for j in finish:  # pragma: no branch
                if nx.has_path(steps, i, j):
                    path = True
                    break
            if path:
                break
        assert path, "No path found between initial and final primary group or node"

        # extend groups
        start = cls.extend_group(steps, start, start_group_name)
        finish = cls.extend_group(steps, finish, finish_group_name)

        # add nodes to graph
        groups = [
            StepGroup(sorted(start), primary=True, group=start_group_name),
            StepGroup(sorted(finish), primary=True, group=finish_group_name),
        ]
        visited = set()
        while True:

            try:
                group = groups.pop(0)
            except IndexError:
                break

            g.add_node(group)

            nodes = set()
            names = set()
            pred = set()
            succ = set()
            for step in group.steps:
                visited.add(step)
                for x in steps.predecessors(step):
                    if x in visited or x in group.steps:
                        continue
                    pred.add(x)
                    names.add(x)
                for x in steps.successors(step):
                    if x in visited or x in group.steps:
                        continue
                    succ.add(x)
                    names.add(x)

            for name in names:
                if name in nodes:
                    continue

                group_name = steps.nodes[name].get('group', None)

                if group_name is None:
                    instance = StepGroup([name])
                else:
                    instance = StepGroup(sorted(cls.extend_group(steps, {name}, group_name)))

                for x in instance.steps:
                    nodes.add(x)

                g.add_node(instance)

                if name in pred:
                    g.add_edge(instance, group)
                if name in succ:
                    g.add_edge(group, instance)

                if instance not in groups:
                    groups.append(instance)

        return g

    @classmethod
    def extend_group(cls, g, data, group_name):
        if group_name is None:
            return data

        response = set()
        count = 0

        for name in sorted(data):
            response.add(name)

            for x in g.predecessors(name):
                if x in data:
                    continue

                group = g.nodes[x].get('group', None)
                if group == group_name:
                    count += 1
                    response.add(x)

            for x in g.successors(name):
                if x in data:
                    continue

                group = g.nodes[x].get('group', None)
                if group == group_name:
                    count += 1
                    response.add(x)

        if count > 0:
            return cls.extend_group(g, response, group_name=group_name)
        return response

    def application_start(self) -> list:

        # test for merges and branches in production groups
        count = 0
        for x in nx.all_topological_sorts(self.production_groups):
            if count == 1:
                raise NotImplementedError("Merges and Branches in production groups are not supported")
            count += 1

        self.app_finish_node = AppNode(name="finish", terminal=True)
        self.app_start_node = AppNode(name="start", terminal=True)

        self.app_active_nodes = None
        self.app_current = None
        self.app_linear = x
        self.app_next_nodes = {self.app_start_node}
        self.app_optimized = None
        self.app_production = nx.DiGraph()
        self.app_transport = {}

        return self.app_linear

    def application_next(self):

        # reset nodes
        self.app_active_nodes = self.app_next_nodes
        self.app_next_nodes = set()

        # get current step
        try:
            self.app_current = self.app_linear.pop(0)
        except IndexError:
            # we've got the last step, add finish node
            for node in self.app_active_nodes:
                self.app_production.add_edge(
                    node, self.app_finish_node,
                    weight=0.0,
                    cls="finish",
                )
            raise StopIteration

        request = market_pb2.Production(
            order=self.instance.identifier,
        )
        for step in self.instance.steps:  # pragma: no branch
            if step.name in self.app_current.steps:
                request.steps.append(step)

        # TODO: for small execution spaces this seems to expensive
        # self.app_transport[self.app_current] = {
        #     "graph": nx.DiGraph(),
        #     "edges": [],
        # }

        return request, self.app_active_nodes

    def application_add(self, response, paths):

        node_i = AppNode(name=self.app_current, agent=response.agent, interface='i')
        node_f = AppNode(name=self.app_current, agent=response.agent, interface='f')

        self.app_next_nodes.add(node_f)
        self.app_production.add_node(node_f)
        self.app_production.add_node(node_i)

        self.app_production.add_edge(
            node_i, node_f,
            cls="production", data=response,
            weight=response.scheduler.cost,
        )

        for node in self.app_active_nodes:
            self.app_production.add_edge(
                node, node_i,
                cls="transport",
                data=self.app_current,
                responses=None,
                weight=0.0,
            )
            # TODO for small executions spaces, this seems to expensive
            # self.app_transport[self.app_current]["edges"].append((node, node_i))

        # act on path
        # TODO for small executions spaces, this seems to expensive
        # for path in paths:
        #     for i in range(1, len(path)):
        #         self.app_transport[self.app_current]["graph"].add_edge(
        #             path[i - 1],
        #             path[i],
        #             weight=0.0,
        #         )

    def application_optimize(self):
        while True:
            cost, path = nx.single_source_dijkstra(self.app_production, self.app_start_node, self.app_finish_node)
            edges = []
            for i in range(len(path) - 1):
                path_i = path[i]
                path_j = path[i + 1]
                edge = self.app_production.edges[path_i, path_j]
                cls = edge.get("cls", None)
                if cls == "transport":
                    if edge["responses"] is None and path_i.agent is not None and path_j.agent is not None:
                        request = market_pb2.Transport(
                            order=self.instance.identifier,
                            # interface=path_i.interface,  # TODO
                            target_agent=path_j.agent,
                            # target_interface=path_j.interface, # TODO
                        )
                        edges.append((path_i.agent, path_j.agent, request, (path_i, path_j)))

            if not edges:
                self.app_optimized = path
                break

            yield edges

    def application_remove(self, node):
        pass

    def application_update(self, edge, responses, delete=False):

        # if delete:
        #     self.app_production.remove_edge(edge)

        # calculate costs and update path
        cost = sum([response.scheduler.cost for response in responses])
        self.app_production.edges[edge].update(responses=responses, weight=cost)

        # update non evaluated paths with detail information from responses
        # TODO but first check how expensive the algorithm is

    def application_apply(self):

        cost, path = nx.single_source_dijkstra(self.app_production, self.app_start_node, self.app_finish_node)

        for x in range(len(path) - 1, 0, -1):
            key = (path[x - 1], path[x])
            edge = self.app_production.edges[key]

            if edge.get('cls') == "transport":
                if edge["responses"] is None:
                    continue
                yield True, edge["responses"]

            elif edge.get('cls') == "production":
                yield False, edge["data"]

    def application_finish(self):
        self._app_current = None
        self._app_linear = None
        self._app_production = None

    def step_start(self, agent, step_name):
        """
        start production step
        """
        save = False
        response = False

        for task in self.instance.tasks:
            if not task.agent == agent:
                continue

            for step in task.production.steps:
                if step.name == step_name:
                    if not step.start:
                        step.start = datetime.utcnow()
                        save = True
                        response = True

            if not task.start:
                task.start = datetime.utcnow()
                save = True

        if save:
            self.save()

        return response

    def step_finish(self, agent, step_name):
        """
        finish production step
        """
        save = False
        response = False

        for task in self.instance.tasks:
            if not task.agent == agent:
                continue

            count = 0
            for step in task.production.steps:
                if step.name == step_name:
                    if not step.start:
                        step.start = datetime.utcnow()
                        save = True
                    if not step.finish:
                        step.finish = datetime.utcnow()
                        save = True
                        response = True

                if not step.finish:
                    count += 1

            if not task.start:
                task.start = datetime.utcnow()
                save = True

            if not count and not task.finish:
                task.finish = datetime.utcnow()
                save = True

        if save:
            self.save()
            self._get_finished_nodes()

        return response

    def as_bytes(self):
        return self.instance.SerializeToString()

    # this function can be monkey-patched to have save callbacks
    def save(self):
        pass

    @abstractmethod
    def load(self, config):  # pragma: no cover
        pass

#!/usr/bin/python
# ex:set fileencoding=utf-8:

import random
import unittest

import networkx as nx

from iams.proto import market_pb2
from iams.interfaces.market import OrderInterface
from iams.interfaces.market import StepGroup


class Order(OrderInterface):

    def load(self, config):
        ability1 = [market_pb2.Ability(name="test1")]
        ability2 = [market_pb2.Ability(name="test2")]
        ability3 = [market_pb2.Ability(name="test3")]
        ability4 = [market_pb2.Ability(name="test4")]
        ability5 = [market_pb2.Ability(name="test5")]

        if config == 'linear':
            data = [
                market_pb2.Step(name='a', edges=['c'], abilities=ability1, group="a"),
                market_pb2.Step(name='b', edges=['c'], abilities=ability1, group="a"),
                market_pb2.Step(name='c', edges=['d'], abilities=ability2),
                market_pb2.Step(name='d', edges=['e'], abilities=ability3),
                market_pb2.Step(name='e', abilities=ability4),
            ]
        elif config == 'branch':
            data = [
                market_pb2.Step(name='a', edges=['b', 'c'], abilities=ability1),
                market_pb2.Step(name='b', abilities=ability2),
                market_pb2.Step(name='c', abilities=ability3, primary=True),
            ]
        elif config == 'merge':
            data = [
                market_pb2.Step(name='a', edges=['c'], abilities=ability1, primary=True),
                market_pb2.Step(name='b', edges=['c'], abilities=ability2),
                market_pb2.Step(name='c', abilities=ability3),
            ]
        else:
            data = [
                market_pb2.Step(name='a', edges=['d'], abilities=ability1, primary=True),
                market_pb2.Step(name='b', edges=['d', 'e'], abilities=ability2),
                market_pb2.Step(name='c', edges=['e'], abilities=ability1),
                market_pb2.Step(name='d', edges=['f', 'g'], abilities=ability3),
                market_pb2.Step(name='e', edges=['g', 'h'], abilities=ability3),
                market_pb2.Step(name='f', abilities=ability4),
                market_pb2.Step(name='g', abilities=ability5, primary=True),
                market_pb2.Step(name='h', abilities=ability4),
            ]

        for step in data:
            self.instance.steps.append(step)


class OrderTests(unittest.TestCase):  # pragma: no cover

    def setUp(self):
        random.seed(6992641887470931864)
        choices = ["test1", "test2", "test3", "test4", "test5"]
        n = 4
        m = 3
        self.abilities = dict([(x, []) for x in choices])
        self.shopfloor = nx.Graph()
        for z in range(1, m + 1):

            namez1 = 'z%02d' % z
            for i in range(1, z):
                namez2 = 'z%02d' % i
                self.shopfloor.add_edge(namez1, namez2, weight=(z - i) * 5)

            for y in range(1, n + 1):

                namey1 = 'y%02d%02d' % (y, z)
                namey2 = 'y%02d%02d' % (y - 1, z)

                if y == 1:
                    self.shopfloor.add_edge(namey1, namez1, weight=1)
                else:
                    self.shopfloor.add_edge(namey1, namey2, weight=0.1)

                for x in range(1, n + 1):

                    name1 = 'M%02d%02d%02d' % (x, y, z)
                    name2 = 'M%02d%02d%02d' % (x - 1, y, z)

                    if x == 1:
                        self.shopfloor.add_edge(name1, namey1, weight=0.1)
                    else:
                        self.shopfloor.add_edge(name1, name2, weight=0.01)

                    ability = random.choice(choices)
                    self.abilities[ability].append(name1)

    # def test_application_complex(self):
    def test_application_linear(self):
        order = Order('test', config='linear')

        # initialize application
        data = [x.steps for x in order.application_start()]
        self.assertEqual(data, [
            ['a', 'b'],
            ['c'],
            ['d'],
            ['e'],
        ])

        while True:
            try:
                request, nodes = order.application_next()
            except StopIteration:
                break

            # search for all machines with abilities in step:
            abilities = set()
            for i in request.steps:
                for j in i.abilities:
                    abilities.add(j.name)
            ability = list(abilities).pop()
            machines = self.abilities[ability]

            for machine in machines:
                # add responses from every machine to application
                response = market_pb2.Task(
                    agent=machine,
                    interface='default',
                    scheduler=market_pb2.Scheduler(
                        cost=random.random() * 4 + 5,
                    ),
                    production=request,
                )

                paths = []
                # TODO: this might be expensive
                # for data in nodes:  # pragma: no branch
                #     if data.agent is None:
                #         continue

                #     distance, path = nx.single_source_dijkstra(self.shopfloor, data.agent, machine)
                #     paths.append(path)

                order.application_add(response, paths)

        # all data added -> start with optimization
        for data in order.application_optimize():
            for i, f, request, edge in data:
                d, path = nx.single_source_dijkstra(self.shopfloor, i, f)
                responses = []
                for p in range(len(path) - 1):
                    path_i = path[p]
                    path_j = path[p + 1]

                    cost = self.shopfloor.edges[path_i, path_j]["weight"]

                    responses.append(market_pb2.Task(
                        agent=path_i,
                        interface='default',
                        scheduler=market_pb2.Scheduler(
                            cost=cost,
                        ),
                        transport=market_pb2.Transport(
                            order=request.order,
                            target_agent=path_j,
                        ),
                    ))
                order.application_update(edge, responses)

        for transport, request in order.application_apply():
            pass

    '''
    def test_application_linear(self):
        order = Order('test', config='linear')
        data = order.application_start()
        self.assertEqual(data, [
            ['a', 'b'],
            ['c'],
            ['d'],
            ['e'],
        ])
    '''

    def test_application_branch(self):
        order = Order('test', config='branch')
        with self.assertRaises(NotImplementedError):
            order.application_start()

    def test_application_merge(self):
        order = Order('test', config='merge')
        with self.assertRaises(NotImplementedError):
            order.application_start()

    def test_as_bytes(self):
        order = Order('test', config=True)
        data = order.as_bytes()
        self.assertEqual(type(data), bytes)

    def test_init_valid(self):
        order = Order('test', steps=[market_pb2.Step(name='a')])
        self.assertEqual(order.instance.steps[0].name, 'a')

    def test_init_undefined_edge(self):
        with self.assertRaises(IndexError):
            Order('test', steps=[market_pb2.Step(name='a', edges=['b'])])

    def test_init_unset_name(self):
        with self.assertRaises(ValueError):
            Order('test', steps=[market_pb2.Step()])

    def test_group_producton_missing_primary_start(self):
        g = nx.DiGraph()
        g.add_node('a', primary=False, group=None)
        g.add_node('b', primary=False, group=None)
        g.add_node('c', primary=False, group=None)
        g.add_edge('a', 'c')
        g.add_edge('b', 'c')

        with self.assertRaises(AssertionError):
            Order.group_production(g)

    def test_group_producton_missing_primary_end(self):
        g = nx.DiGraph()
        g.add_node('a', primary=False, group=None)
        g.add_node('b', primary=False, group=None)
        g.add_node('c', primary=False, group=None)
        g.add_edge('a', 'b')
        g.add_edge('a', 'c')

        with self.assertRaises(AssertionError):
            Order.group_production(g)

    def test_group_producton_two_primary_start(self):
        g = nx.DiGraph()
        g.add_node('a', primary=True, group=None)
        g.add_node('b', primary=True, group=None)
        g.add_node('c', primary=True, group=None)
        g.add_edge('a', 'c')
        g.add_edge('b', 'c')

        with self.assertRaises(AssertionError):
            Order.group_production(g)

    def test_group_producton_two_primary_end(self):
        g = nx.DiGraph()
        g.add_node('a', primary=True, group=None)
        g.add_node('b', primary=True, group=None)
        g.add_node('c', primary=True, group=None)
        g.add_edge('a', 'b')
        g.add_edge('a', 'c')

        with self.assertRaises(AssertionError):
            Order.group_production(g)

    def test_group_producton_cyclic(self):
        g = nx.DiGraph()
        g.add_node('a')
        g.add_node('b')
        g.add_edge('a', 'b')
        g.add_edge('b', 'a')

        with self.assertRaises(AssertionError):
            Order.group_production(g)

    def test_group_producton_no_primary_path(self):
        g = nx.DiGraph()
        g.add_node('a', primary=True, group='A')
        g.add_node('b', primary=True, group='A')
        g.add_node('c', primary=False, group=None)
        g.add_node('d', primary=False, group=None)
        g.add_node('e', primary=True, group='B')
        g.add_node('f', primary=True, group='B')
        g.add_edge('a', 'c')
        g.add_edge('b', 'c')
        g.add_edge('d', 'e')
        g.add_edge('d', 'f')

        with self.assertRaises(AssertionError):
            Order.group_production(g)

    def test_group_producton_merge(self):
        g = nx.DiGraph()
        g.add_node('a', primary=True)
        g.add_node('b')
        g.add_node('c')
        g.add_edge('a', 'c')
        g.add_edge('b', 'c')

        g = Order.group_production(g)

        a = StepGroup(['a'], primary=True)
        b = StepGroup(['b'], primary=False)
        c = StepGroup(['c'], primary=True)
        self.assertEqual(set(g.nodes.keys()), {a, b, c})
        self.assertEqual(set(g.edges.keys()), {(a, c), (b, c)})

    def test_group_producton_branch(self):
        g = nx.DiGraph()
        g.add_node('a')
        g.add_node('b')
        g.add_node('c', primary=True)
        g.add_edge('a', 'b')
        g.add_edge('a', 'c')

        g = Order.group_production(g)

        a = StepGroup(['a'], primary=True)
        b = StepGroup(['b'], primary=False)
        c = StepGroup(['c'], primary=True)
        self.assertEqual(set(g.nodes.keys()), {a, b, c})
        self.assertEqual(set(g.edges.keys()), {(a, b), (a, c)})

    def test_group_producton_simple(self):
        g = nx.DiGraph()
        g.add_node('a')
        g = Order.group_production(g)
        self.assertEqual(list(g.nodes.keys()), [StepGroup(['a'], primary=True)])

    def test_group_producton_valid(self):
        g = nx.DiGraph()
        g.add_node('a', primary=True, group='A')
        g.add_node('b', group='A')
        g.add_node('c', group='A')
        g.add_node('d')
        g.add_node('e', group='A')
        g.add_node('f', group='A')
        g.add_node('g', group='A')
        g.add_node('h', group='H')
        g.add_node('i', group='H')
        g.add_node('j', primary=True, group='H')

        g.add_edge('a', 'c')
        g.add_edge('b', 'c')
        g.add_edge('c', 'd')
        g.add_edge('d', 'e')
        g.add_edge('d', 'f')
        g.add_edge('e', 'g')
        g.add_edge('f', 'g')
        g.add_edge('g', 'h')
        g.add_edge('h', 'i')
        g.add_edge('h', 'j')

        g = Order.group_production(g)

        a = StepGroup(['a', 'b', 'c'], primary=True)
        d = StepGroup(['d'])
        e = StepGroup(['e', 'f', 'g'])
        h = StepGroup(['h', 'i', 'j'], primary=True)

        self.assertEqual(set(g.nodes.keys()), {a, d, e, h})
        self.assertEqual(set(g.edges.keys()), {(a, d), (d, e), (e, h)})

#!/usr/bin/python
# ex:set fileencoding=utf-8:

import unittest

from iams.recipe import Graph
from iams.recipe import RecepieData


class RecipeTests(unittest.TestCase):

    def test_split(self):
        graph = Graph()
        graph.load([
            RecepieData("X", edges=['A1', 'A2'], split=True),
            RecepieData("A1", edges=['B1']),
            RecepieData("A2", edges=['B2']),
            RecepieData("B1", edges=['D']),
            RecepieData("B2", edges=['D']),
            RecepieData("D"),
        ])

        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'A1')
        self.assertEqual(nodes[1].name, 'A2')

        graph.finish(nodes[0])
        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'B1')

        self.assertEqual(len(graph.g), 2)

    def test_graph(self):
        graph = Graph()
        graph.load([
            RecepieData("A", edges=['C']),
            RecepieData("B", edges=['C']),
            RecepieData("C"),
        ])

        self.assertEqual(bool(graph), True)

        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'A')
        self.assertEqual(nodes[1].name, 'B')

        graph.finish(nodes[0])
        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'B')

        graph.finish(nodes[0])
        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'C')

        graph.finish(nodes[0])
        self.assertEqual(len(graph.g), 0)

        with self.assertRaises(StopIteration):
            next(graph)

        self.assertEqual(bool(graph), False)


if __name__ == '__main__':
    unittest.main()

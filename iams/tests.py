#!/usr/bin/python
# ex:set fileencoding=utf-8:

import unittest

from iams.recipe import Recipe
from iams.recipe import RecipeData


class RecipeTests(unittest.TestCase):

    def test_split(self):
        graph = Recipe([
            RecipeData("X", edges=['A1', 'A2'], split=True),
            RecipeData("A1", edges=['B1']),
            RecipeData("A2", edges=['B2']),
            RecipeData("B1", edges=['D']),
            RecipeData("B2", edges=['D']),
            RecipeData("D"),
        ])

        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'A1')
        self.assertEqual(nodes[1].name, 'A2')

        graph(nodes[0])
        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'B1')

        self.assertEqual(len(graph.g), 2)

    def test_graph(self):
        graph = Recipe([
            RecipeData("A", edges=['C']),
            RecipeData("B", edges=['C']),
            RecipeData("C"),
        ])

        self.assertEqual(bool(graph), True)

        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'A')
        self.assertEqual(nodes[1].name, 'B')

        graph(nodes[0])
        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'B')

        graph(nodes[0])
        nodes = next(graph)
        self.assertEqual(nodes[0].name, 'C')

        graph(nodes[0])
        self.assertEqual(len(graph.g), 0)

        with self.assertRaises(StopIteration):
            next(graph)

        self.assertEqual(bool(graph), False)


if __name__ == '__main__':
    unittest.main()

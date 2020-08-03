#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import logging

import networkx as nx

from abc import ABC
from abc import abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field


logger = logging.getLogger(__name__)


class RecipeInterface(ABC):

    def __iter__(self):  # pragma: no cover
        return self

    @abstractmethod
    def __init__(self, steps):  # pragma: no cover
        """
        """
        pass

    @abstractmethod
    def __bool__(self):  # pragma: no cover
        """
        True if steps are available
        """
        pass

    @abstractmethod
    def __next__(self):  # pragma: no cover
        """
        returns currently available steps
        """
        pass

    @abstractmethod
    def __call__(self, step):  # pragma: no cover
        """
        finishes step
        """
        pass

    def copy(self):  # pragma: no cover
        """
        returns deepcopy of recipe
        """
        return deepcopy(self)


@dataclass(order=['-level', 'name'])
class RecipeData:
    name: str = field(compare=True, hash=True)
    edges: list = field(default_factory=list, repr=False, hash=None)
    split: bool = field(compare=False, hash=False, default=False)
    level: int = field(default=0, repr=True, init=False, compare=False)
    ability: str = field(compare=False, hash=False, repr=False, default=None)
    properties: dict = field(compare=False, hash=False, repr=False, default_factory=dict)
    material: str = field(compare=False, hash=False, repr=False, default=None)
    quantitiy: int = field(compare=False, hash=False, repr=False, default=0)

    def __str__(self):
        return self.name


class Recipe(RecipeInterface):

    def __init__(self, recepie):
        """
        """
        logger.debug("Loading graph from recepie")
        self.g = nx.DiGraph()
        self.history = []
        for line in recepie:
            self.g.add_node(line.name, data=line)
            for edge in line.edges:
                self.g.add_edge(line.name, edge)
        self._calculate_levels()

    def __next__(self):
        """
        select and return all active nodes
        """
        nodes = []

        # which nodes have no predecessors
        for node_name in self.g.nodes.keys():
            node = self.g.nodes[node_name]["data"]

            if sum([1 for x in self.g.predecessors(node.name)]) == 0:
                if node.split:
                    for x in self.g.successors(node.name):
                        nodes.append(self.g.nodes[x]["data"])
                else:
                    nodes.append(node)

        if not nodes:
            logger.debug("No nodes found - stop iteration")
            raise StopIteration

        nodes.sort()
        logger.debug("Found active nodes: %s", nodes)
        return nodes

    def __bool__(self):
        return bool(len(self.g))

    def _calculate_levels(self):
        g = deepcopy(self.g)
        level = 1

        while True:
            nodes = []
            for node_name in g.nodes.keys():
                node = self.g.nodes[node_name]["data"]

                if sum([1 for x in g.predecessors(node.name)]) == 0:
                    node.level = level
                    nodes.append(node.name)

            for node in nodes:
                g.remove_node(node)

            if not nodes:
                logger.info("calculated levels")
                break
            level += 1

    def __call__(self, node: RecipeData) -> bool:
        """
        marks the given node as done
        """

        # find siblings
        parents = []
        siblings = []
        for x in self.g.predecessors(node.name):
            data = self.g.nodes[x]["data"]
            if not data.split:
                raise IndexError("Node '%s' has connected parents and cannot be finished" % node.name)

            # store parent split nodes
            parents.append(x)

            # find all siblings
            for y in self.g.successors(x):
                if node.name == y:
                    continue
                siblings.append(y)

        logger.debug("removing parent nodes: %s", parents)
        for x in parents:
            # remove split node
            self.g.remove_node(x)

        logger.debug("found siblings: %s", siblings)

        # remove the not anymore used sibling paths
        while True:
            try:
                sibling = siblings.pop(0)
            except IndexError:
                break

            for y in self.g.successors(sibling):
                count = sum([1 for x in self.g.predecessors(y)])
                if count == 1:
                    siblings.append(y)

            self.g.remove_node(sibling)
            logger.debug("removing sibling: %s", sibling)

        # delete node from graph
        self.g.remove_node(node.name)

        # add node to history
        self.history.append(node)


if __name__ == "__main__":  # pragma: no cover

    import random
    from logging.config import dictConfig
    from iams.helper import get_logging_config

    dictConfig(get_logging_config([], logging.DEBUG))

    DATA = [
        RecipeData("A", edges=['C']),
        RecipeData("B", edges=['C']),
        RecipeData("C", edges=['D']),
        RecipeData("D", edges=['A1', 'A2']),
        RecipeData("A1", edges=['R1', 'R2']),
        RecipeData("A2", edges=['R3', 'R4']),
        RecipeData("R1", edges=['S1']),
        RecipeData("R2", edges=['S2']),
        RecipeData("R3", edges=['S3']),
        RecipeData("R4", edges=['S4']),
        RecipeData("S1", edges=['F']),
        RecipeData("S2", edges=['F']),
        RecipeData("S3", edges=['F']),
        RecipeData("S4", edges=['F']),
        RecipeData("F", edges=["G1", "G2", "G3"], split=True),
        RecipeData("G1", edges=['H11', 'H12', 'H13']),
        RecipeData("G2", edges=['H21', 'H22', 'H23']),
        RecipeData("G3", edges=['H31', 'H32', 'H33']),
        RecipeData("H11", edges=['I', 'J']),
        RecipeData("H12", edges=['I', 'J']),
        RecipeData("H13", edges=['I', 'J']),
        RecipeData("H21", edges=['I', 'J']),
        RecipeData("H22", edges=['I', 'J']),
        RecipeData("H23", edges=['I', 'J']),
        RecipeData("H31", edges=['I', 'J']),
        RecipeData("H32", edges=['I', 'J']),
        RecipeData("H33", edges=['I', 'J']),
        RecipeData("I"),
        RecipeData("J"),
    ]

    for x in range(1):
        logger.info("Run %s", x + 1)
        g = Recipe(DATA)
        for active_nodes in g:
            node = random.choice(active_nodes)  # pick random node
            logger.info("Doing task %s", node)
            g(node)  # finish picked node
        logger.debug("history %s", g.history)

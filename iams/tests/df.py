#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test df
"""

import logging

import networkx as nx


from iams.interfaces.df import DirectoryFacilitatorInterface

logger = logging.getLogger(__name__)


class DF(DirectoryFacilitatorInterface):
    """
    Directory facilitator used in tests and simulations as it does not store its state
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.topology = None

    def __call__(self):
        self.topology = nx.DiGraph()

    def agents(self, **kwargs):
        for agent, data in self.topology.nodes.items():
            valid = True
            for key, value in kwargs.items():
                try:
                    if data[key] != value:
                        valid = False
                except KeyError:
                    valid = False
            if valid:
                yield (agent, data)

    def register_agent(self, name, **kwargs):
        if name in self.topology:
            self.topology.nodes[name].clear()
            self.topology.nodes[name].update(kwargs)
        else:
            self.topology.add_node(name, **kwargs)

#   def agent_unregister(self, name):
#       self.topology.remove_node(name)

#   def agent_register_connection(self, agent, other, bidirectional=False, weight=-1.0):
#       raise NotImplementedError
#       self.topology.add_edge(str(agent), str(other), weight=weight)
#       if bidirectional:
#           self.topology.add_edge(str(other), str(agent), weight=weight)

#   def agent_unregister_connection(self, agent, other, bidirectional=False):
#       raise NotImplementedError
#       self.topology.remove_edge(str(agent), str(other))
#       if bidirectional:
#           self.topology.remove_edge(str(other), str(agent))

#   def agent_update_connection(self, agent, other, weight):
#       raise NotImplementedError

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

import networkx as nx


logger = logging.getLogger(__name__)


class DF(object):

    def __call__(self):
        self.topology = nx.DiGraph()

    def agent_register(self, agent):
        self.topology.add_node(str(agent), instance=agent)

    def agent_unregister(self, agent):
        self.topology.remove_node(str(agent))

    def agent_register_connection(self, agent, other, bidirectional=False, weight=-1.0):
        self.topology.add_edge(str(agent), str(other), weight=weight)
        if bidirectional:
            self.topology.add_edge(str(other), str(agent), weight=weight)

    def agent_unregister_connection(self, agent, other, bidirectional=False):
        self.topology.remove_edge(str(agent), str(other))
        if bidirectional:
            self.topology.remove_edge(str(other), str(agent))

    def agent_update_connection(self, agent, other, weight):
        raise NotImplementedError

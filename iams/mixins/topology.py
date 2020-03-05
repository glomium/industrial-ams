#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
# import networkx as nx

logger = logging.getLogger(__name__)


class TopologyMixin(object):
    """
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._topology_cache = {}

    def _start(self, *args, **kwargs):
        super()._start(*args, **kwargs)

    def get_topology(self):
        # get a list of agents
        agents = []
        for labels in self.order_agent_labels():
            for agent in self._iams.get_agents(labels):
                agents.append(agent.name)

        # futures = []
        # # get all agents via label
        # for agent in agents:
        #     logger.debug("Adding %s to queue", agent)
        #     futures.append(self._executor.submit(
        #         self.add_application,
        #         agent.name,
        #         previous,
        #         request,
        #         eta,
        #         False,
        #     ))
        # concurrent.futures.wait(futures)

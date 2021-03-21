#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from random import choices
from random import shuffle

from iams.utils.arangodb import Arango
from iams.proto.framework_pb2 import Edge
from iams.proto.framework_pb2 import Node


try:
    from arango import ArangoClient
    client = ArangoClient(hosts='http://localhost:8529')
    db = client.db("_system", username="root", password="root", verify=True)
    if db.has_database("iams_test"):
        db.delete_database("iams_test")
except Exception as e:  # pragma: no cover
    SKIP = str(e)
else:
    SKIP = None


ABILITIES = ["A", "B", "C", "D", "E", "F", "G"]


class IMS(object):
    def __init__(self, name, b1=None, b2=None):
        self.name = name
        self.b1 = b1
        self.b2 = b2

        abilities = list(set(choices(ABILITIES, k=3)))
        edges = self.get_edges()

        self.node = Node(
            default="B1",
            pools=["ims"],
            abilities=abilities,
            edges=edges,
        )

    def get_edges(self):
        data = []
        for edge in self.edges():
            data.append(Edge(**edge))
        return data

    def edges(self):
        yield {
            "node_from": "B1",
            "node_to": "B2",
            "weight": 2.0,
        }
        yield {
            "node_from": "B1",
            "node_to": "P",
            "weight": 1.2,
        }
        yield {
            "node_from": "P",
            "node_to": "B2",
            "weight": 1.2,
        }
        yield {
            "node_from": "P",
            "node_to": "B1",
            "weight": 1.2,
        }
        yield {
            "node_from": "B2",
            "node_to": "B1",
            "weight": 2.0,
        }

        if self.b1:
            a, e = self.b1.split(':')
            yield {
                "node_from": "B1",
                "node_to": e,
                "agent": a,
                "weight": 1.0,
            }
        if self.b2:
            a, e = self.b2.split(':')
            yield {
                "node_from": "B2",
                "node_to": e,
                "agent": a,
                "weight": 1.0,
            }


class UR(object):

    def __init__(self, name, p1=None, p2=None, p3=None, p4=None):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4
        self.name = name

        self.node = Node(
            default="T1",
            edges=self.get_edges(),
        )

    def get_edges(self):
        data = []
        for edge in self.edges():
            data.append(Edge(**edge))
        return data

    def edges(self):
        yield {
            "node_from": "P1",
            "node_to": "T1",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "node_from": "P2",
            "node_to": "T1",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "node_from": "P1",
            "node_to": "P2",
            "weight": 1.0,
            "symmetric": True,
        }

        yield {
            "node_from": "T1",
            "node_to": "T2",
            "weight": 1.0,
            "symmetric": True,
        }

        yield {
            "node_from": "P3",
            "node_to": "T2",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "node_from": "P4",
            "node_to": "T2",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "node_from": "P3",
            "node_to": "P4",
            "weight": 1.0,
            "symmetric": True,
        }

        if self.p1:
            a, e = self.p1.split(':')
            yield {
                "node_from": "P1",
                "node_to": e,
                "agent": a,
                "weight": 1.0,
                "symmetric": True,
            }
        if self.p2:
            a, e = self.p2.split(':')
            yield {
                "node_from": "P2",
                "node_to": e,
                "agent": a,
                "weight": 1.0,
                "symmetric": True,
            }
        if self.p3:
            a, e = self.p3.split(':')
            yield {
                "node_from": "P3",
                "node_to": e,
                "agent": a,
                "weight": 1.0,
                "symmetric": True,
            }
        if self.p4:
            a, e = self.p4.split(':')
            yield {
                "node_from": "P4",
                "node_to": e,
                "agent": a,
                "weight": 1.0,
                "symmetric": True,
            }


# @unittest.skipIf(SKIP is not None, SKIP)
@unittest.skip
class ImportTests(unittest.TestCase):  # pragma: no cover
    def test_empty(self):
        agents = [
            IMS("IMS11", "IMS17:B2", "IMS13A:B1"),
            IMS("IMS13A", "IMS11:B2", "IMS13B:B1"),
            IMS("IMS13B", "IMS13A:B2", "IMS14A:B1"),
            IMS("IMS14A", "IMS13B:B2", "IMS14B:B1"),
            IMS("IMS14B", "IMS14A:B2", "IMS15A:B1"),
            IMS("IMS15A", "IMS14B:B2", "IMS15B:B1"),
            IMS("IMS15B", "IMS15A:B2", "IMS17:B1"),
            IMS("IMS17", "IMS15B:B2", "IMS11:B1"),
            UR("UR3A", "IMS15B:B2", "IMS16:B1"),
            IMS("IMS16"),

            IMS("IMS23A", b2="IMS23B:B1"),
            IMS("IMS23B", b1="IMS23A:B2"),
            IMS("IMS24A", b2="IMS24B:B1"),
            IMS("IMS24B", b1="IMS24A:B2"),
            IMS("IMS25A", b2="IMS25B:B1"),
            IMS("IMS25B", b1="IMS25A:B2"),
            UR("UR3B", "IMS23B:B2", "IMS24B:B2", "IMS25A:B1", "IMS21:B1"),
            IMS("IMS21", b2="IMS26:B1"),
            IMS("IMS26", b2="IMS27A:B1"),
            IMS("IMS27A", b2="IMS27B:B1"),
            IMS("IMS27B", b2="IMS21:B1"),
        ]
        shuffle(agents)

        instance = Arango("test", hosts="http://localhost:8529", password="root")

        for agent in agents:
            instance.create_agent(agent.name, agent.node)
            instance.update_agent(agent.name, agent.node)

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from arango import ArangoClient
from arango.exceptions import ServerConnectionError

logger = logging.getLogger(__name__)


class Arango(object):

    def __init__(self, database, username="root", password=None, hosts="http://tasks.arango:8529"):
        client = ArangoClient(hosts=hosts)

        # TODO make read from secrets file optional
        # (specify environment variables or settings to make this configurable)
        if password is None:
            with open('/run/secrets/arango', 'r') as f:
                password = f.read()

        # setup database
        try:
            self.db = client.db(database, username=username, password=password, verify=True)
        except ServerConnectionError:
            if username == "root":
                logger.info("creating arango database %s", database)
                client.db(username=username, password=password).create_database(database)
            else:
                raise
            self.db = client.db(database, username=username, password=password, verify=True)

        # setup collections
        for collection in ["topology", "agent", "pool"]:
            if not self.db.has_collection(collection):
                self.db.create_collection(collection)

        for edge in ["directed", "symmetric", "logical", "virtual"]:
            if not self.db.has_collection(edge):
                self.db.create_collection(edge, edge=True)

        # setup graphs
        if not self.db.has_graph('plants'):
            self.db.create_graph('plants', edge_definitions=[{
                "edge_collection": "symmetric",
                "from_vertex_collections": ["topology"],
                "to_vertex_collections": ["topology"],
            }, {
                "edge_collection": "directed",
                "from_vertex_collections": ["topology"],
                "to_vertex_collections": ["topology"],
            }])

        if not self.db.has_graph('connections'):
            self.db.create_graph('connections', edge_definitions=[{
                "edge_collection": "logical",
                "from_vertex_collections": ["agent", "pool"],
                "to_vertex_collections": ["agent", "pool"],
            }])
            # }, {
            #     "edge_collection": "virtual",
            #     "from_vertex_collections": ["agent"],
            #     "to_vertex_collections": ["agent"],

    def create_agent(self, name, edges, pool=None):
        nodes = []
        if pool:
            self.db.collection("agent").insert({
                "_key": name,
                "update": True,
                "pool": pool,
            })
        else:
            self.db.collection("agent").insert({
                "_key": name,
                "update": True,
            })

        for edge in edges:

            if edge["from"] not in nodes:
                self.db.collection("topology").insert({
                    "_key": f"{name}:{edge['from']}",
                    "agent": f"agent/{name}",
                })
                nodes.append(edge["from"])

            if edge["to"] not in nodes:
                self.db.collection("topology").insert({
                    "_key": f"{name}:{edge['to']}",
                    "agent": f"agent/{name}",
                })
                nodes.append(edge["to"])

            if edge.get("symmetric", False) is True:
                collection = "symmetric"
            else:
                collection = "directed"

            if ":" in edge["to"]:
                self.db.collection(collection).insert({
                    "_from": f"topology/{name}:{edge['from']}",
                    "_to": f"topology/{edge['to']}",
                    "weight": edge["weight"],
                })

                # agent instance connected to this node needs to be updated
                if collection == "symmetric":
                    node = edge["to"].split(":")[0]
                    data = self.db.collection('agent').get({"_key": node})
                    logger.info("set update on %s", node)
                    if data is None:
                        continue
                    data["update"] = True
                    self.db.collection('agent').update(data)

            else:
                self.db.collection(collection).insert({
                    "_from": f"topology/{name}:{edge['from']}",
                    "_to": f"topology/{name}:{edge['to']}",
                    "weight": edge["weight"],
                })
        self.update_agents()

    def delete_agent(self, name, update=True):
        query1 = """
        LET edge = (FOR t IN topology FILTER t.agent == @agent LIMIT 1 RETURN t._id)[0]
        LET related = (FOR v, e IN 0..100 OUTBOUND edge directed, ANY symmetric
            PRUNE v.agent != @agent
            OPTIONS {bfs: true, uniqueVertices: 'global'}
            FILTER v.agent != @agent
            UPDATE PARSE_IDENTIFIER(v.agent).key WITH {"update": True} IN agent)
        FOR doc IN topology
            FILTER doc.agent == @agent
            LET rs = (FOR es IN symmetric FILTER es._from == doc.id REMOVE es IN symmetric)
            LET rd = (FOR ed IN directed FILTER ed._from == doc.id REMOVE ed IN directed)
            REMOVE doc in topology
        """
        query2 = """
        LET l = (FOR v, e IN 1..1 ANY @agent
            GRAPH 'connections'
            REMOVE e._key IN logical OPTIONS { ignoreErrors: true }
            REMOVE e._key IN virtual OPTIONS { ignoreErrors: true })
        REMOVE PARSE_IDENTIFIER(@agent).key IN agent
        """
        self.db.aql.execute(query1, bind_vars={"agent": "agent/" + name})
        self.db.aql.execute(query2, bind_vars={"agent": "agent/" + name})
        if update:
            self.update_agents()

    def update_agent(self, name, edges, pool=None):
        self.delete_agent(name, update=False)
        self.create_agent(name, edges, pool)

    def update_agents(self):
        """
        iterates over all agents with update == true and updates their data
        """
        for data in self.db.collection('agent').find({"update": True}):
            pass
            # get neighbor agents
            pk = data["_id"]
            query = f"""
            WITH symmetric, directed
            LET edge = (FOR doc IN topology FILTER doc.agent == '{pk}' LIMIT 1 RETURN doc._id)[0]
            FOR v, e IN 1..100 OUTBOUND edge ANY symmetric, directed
                PRUNE v.agent != '{pk}'
                OPTIONS {{bfs: true, uniqueVertices: 'global'}}
                FILTER v.agent != '{pk}'
                SORT v._id
                LET agent = (FOR doc IN agent FILTER doc._id == v.agent LIMIT 1 RETURN doc)[0]
                RETURN agent
            """

            # select all connections
            nodes = {}
            update = False
            for i in self.db.aql.execute(query):
                if i is None:
                    update = True
                    continue
                nodes[i["_id"]] = i

            # skip logical and virtual connected nodes
            for edge in self.db.collection("logical").find({"_from": data["_id"]}):
                if edge["_to"] in nodes:
                    nodes.pop(edge["_to"])
            for edge in self.db.collection("virtual").find({"_from": data["_id"]}):
                if edge["_to"] in nodes:
                    nodes.pop(edge["_to"])

            # add new nodes
            for node in nodes.values():
                if "pool" in data or "pool" in node:
                    collection = "virtual"
                else:
                    collection = "logical"

                self.db.collection(collection).insert({
                    "_from": data["_id"],
                    "_to": node["_id"],
                })

            # update if fully loaded
            if data["update"] != update:
                data["update"] = update
                self.db.collection('agent').update(data)

            # add to automatically generated pool
            if update is False and "pool" in data:
                pk = data["_id"]
                pool = data["pool"]

                query = f"""
                WITH logical, virtual
                FOR v, e IN 1..100 INBOUND '{pk}' logical, virtual
                    PRUNE v.pool != '{pool}'
                    OPTIONS {{bfs: true, uniqueVertices: 'global'}}
                    FILTER IS_SAME_COLLECTION('pool', v) AND v.cls == '{pool}'
                    SORT v._id
                    RETURN v
                """
                pool = None
                for i, p in enumerate(self.db.aql.execute(query)):
                    if i == 0:
                        pool = p
                        continue

                    for edge in self.db.collection('logical').find({"_from": p["_id"]}):
                        edge["_from"] = pool['_id']
                        self.db.collection('logical').update(edge)

                    for edge in self.db.collection('logical').find({"_to": p["_id"]}):
                        edge["_to"] = pool['_id']
                        self.db.collection('logical').update(edge)

                    self.db.collection('pool').delete(p)

                if pool is None:
                    pool = self.db.collection("pool").insert({"cls": data["pool"]})

                edges = list(self.db.collection('logical').find({"_from": pool["_id"], "_to": data["_id"]}))
                if len(edges) == 0:
                    self.db.collection('logical').insert({
                        "_from": pool["_id"],
                        "_to": data["_id"],
                    })
                edges = list(self.db.collection('logical').find({"_to": pool["_id"], "_from": data["_id"]}))
                if len(edges) == 0:
                    self.db.collection('logical').insert({
                        "_to": pool["_id"],
                        "_from": data["_id"],
                    })

                # add connections to pools from neighbours (outbound connections)
                query = f"""
                FOR v, e IN 2..2 OUTBOUND '{pool["_id"]}' logical, virtual
                OPTIONS {{bfs: true, uniqueVertices: 'global'}}
                FILTER IS_SAME_COLLECTION('virtual', e) && v.pool != '{data["pool"]}'
                RETURN v
                """
                for node in self.db.aql.execute(query):
                    edges = list(self.db.collection('logical').find({"_from": pool["_id"], "_to": node["_id"]}))
                    if len(edges) == 0:
                        self.db.collection('logical').insert({
                            "_from": pool["_id"],
                            "_to": node["_id"],
                        })

                # add connections to pools from neighbours (inbound connections)
                query = f"""
                FOR v, e IN 2..2 INBOUND '{pool["_id"]}' logical, virtual
                OPTIONS {{bfs: true, uniqueVertices: 'global'}}
                FILTER IS_SAME_COLLECTION('virtual', e) && v.pool != '{data["pool"]}'
                RETURN v
                """
                for node in self.db.aql.execute(query):
                    edges = list(self.db.collection('logical').find({"_to": pool["_id"], "_from": node["_id"]}))
                    if len(edges) == 0:
                        self.db.collection('logical').insert({
                            "_to": pool["_id"],
                            "_from": node["_id"],
                        })


class IMS(object):

    def __init__(self, name, b1=None, b2=None):
        self.name = name
        self.pool = "ims"
        self.b1 = b1
        self.b2 = b2

    def edges(self):
        yield {
            "from": f"B1",
            "to": f"B2",
            "weight": 2.0,
        }
        yield {
            "from": f"B1",
            "to": f"P",
            "weight": 1.2,
        }
        yield {
            "from": f"P",
            "to": f"B2",
            "weight": 1.2,
        }
        yield {
            "from": f"P",
            "to": f"B1",
            "weight": 1.2,
        }
        yield {
            "from": f"B2",
            "to": f"B1",
            "weight": 2.0,
        }

        if self.b1:
            yield {
                "from": f"B1",
                "to": f"{self.b1}",
                "weight": 1.0,
            }
        if self.b2:
            yield {
                "from": f"B2",
                "to": f"{self.b2}",
                "weight": 1.0,
            }


class UR(object):

    def __init__(self, name, p1=None, p2=None, p3=None, p4=None):
        self.name = name
        self.pool = None
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4

    def edges(self):
        yield {
            "from": f"P1",
            "to": f"T1",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "from": f"P2",
            "to": f"T1",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "from": f"P1",
            "to": f"P2",
            "weight": 1.0,
            "symmetric": True,
        }

        yield {
            "from": f"T1",
            "to": f"T2",
            "weight": 1.0,
            "symmetric": True,
        }

        yield {
            "from": f"P3",
            "to": f"T2",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "from": f"P4",
            "to": f"T2",
            "weight": 1.0,
            "symmetric": True,
        }
        yield {
            "from": f"P3",
            "to": f"P4",
            "weight": 1.0,
            "symmetric": True,
        }

        if self.p1:
            yield {
                "from": f"P1",
                "to": f"{self.p1}",
                "weight": 1.0,
                "symmetric": True,
            }
        if self.p2:
            yield {
                "from": f"P2",
                "to": f"{self.p2}",
                "weight": 1.0,
                "symmetric": True,
            }
        if self.p3:
            yield {
                "from": f"P3",
                "to": f"{self.p3}",
                "weight": 1.0,
                "symmetric": True,
            }
        if self.p4:
            yield {
                "from": f"P4",
                "to": f"{self.p4}",
                "weight": 1.0,
                "symmetric": True,
            }


if __name__ == "__main__":

    from random import shuffle

    AGENTS = [
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
    shuffle(AGENTS)

    client = ArangoClient(hosts='http://localhost:8529')
    db = client.db("_system", username="root", password="root", verify=True)
    if db.has_database("iams-prod"):
        db.delete_database("iams-prod")
    instance = Arango("iams-prod", hosts="http://localhost:8529", password="root")

    for agent in AGENTS:
        print("===", agent.name, "=" * (75 - len(agent.name)))  # noqa
        edges = list(agent.edges())
        instance.create_agent(agent.name, edges, agent.pool)
    instance.update_agent(agent.name, edges, agent.pool)

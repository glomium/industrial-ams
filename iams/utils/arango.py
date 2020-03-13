#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

from random import shuffle, seed

from arango import ArangoClient


seed("arango test")

# Initialize the client for ArangoDB.
client = ArangoClient(hosts='http://localhost:8529')

database = "prod"
username = "root"
password = "root"

# SETUP

db = client.db(username=username, password=password)
if not db.has_database(database):
    db.create_database(database)
else:
    db.delete_database(database)
    db.create_database(database)

db = client.db(database, username=username, password=password)

for collection in ["topology", "agent", "pool"]:
    if not db.has_collection(collection):
        db.create_collection(collection)

for edge in ["directed", "symmetric", "logical", "virtual"]:
    if not db.has_collection(edge):
        db.create_collection(edge, edge=True)

if db.has_graph('plants'):
    graph = db.graph('plants')

else:
    graph = db.create_graph('plants', edge_definitions=[{
        "edge_collection": "symmetric",
        "from_vertex_collections": ["topology"],
        "to_vertex_collections": ["topology"],
    }, {
        "edge_collection": "directed",
        "from_vertex_collections": ["topology"],
        "to_vertex_collections": ["topology"],
    }])

if db.has_graph('connections'):
    graph = db.graph('connections')
else:
    graph = db.create_graph('connections', edge_definitions=[{
        "edge_collection": "logical",
        "from_vertex_collections": ["agent", "pool"],
        "to_vertex_collections": ["agent", "pool"],
    }])
    # }, {
    #     "edge_collection": "virtual",
    #     "from_vertex_collections": ["agent"],
    #     "to_vertex_collections": ["agent"],


class IMS(object):

    def __init__(self, name, b1=None, b2=None):
        self.name = name
        self.b1 = b1
        self.b2 = b2

    def nodes(self):
        yield "agent", {"_key": f"{self.name}", "update": True, "pool": "ims-carrier"}
        yield "topology", {"_key": f"{self.name}:B1", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:B2", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:P", "agent": f"agent/{self.name}"}

    def edges(self):
        yield "directed", {
            "_from": f"topology/{self.name}:B1",
            "_to": f"topology/{self.name}:B2",
            "weight": 2.0,
        }
        yield "directed", {
            "_from": f"topology/{self.name}:B1",
            "_to": f"topology/{self.name}:P",
            "weight": 1.2,
        }
        yield "directed", {
            "_from": f"topology/{self.name}:P",
            "_to": f"topology/{self.name}:B2",
            "weight": 1.2,
        }
        yield "directed", {
            "_from": f"topology/{self.name}:P",
            "_to": f"topology/{self.name}:B1",
            "weight": 1.2,
        }
        yield "directed", {
            "_from": f"topology/{self.name}:B2",
            "_to": f"topology/{self.name}:B1",
            "weight": 2.0,
        }

        if self.b1:
            yield "directed", {
                "_from": f"topology/{self.name}:B1",
                "_to": f"topology/{self.b1}",
                "weight": 1.0,
            }
        if self.b2:
            yield "directed", {
                "_from": f"topology/{self.name}:B2",
                "_to": f"topology/{self.b2}",
                "weight": 1.0,
            }


class UR(object):

    def __init__(self, name, p1=None, p2=None, p3=None, p4=None):
        self.name = name
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
        self.p4 = p4

    def nodes(self):
        yield "agent", {"_key": f"{self.name}", "update": True}
        yield "topology", {"_key": f"{self.name}:P1", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:P2", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:P3", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:P4", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:T1", "agent": f"agent/{self.name}"}
        yield "topology", {"_key": f"{self.name}:T2", "agent": f"agent/{self.name}"}

    def edges(self):
        yield "symmetric", {
            "_from": f"topology/{self.name}:P1",
            "_to": f"topology/{self.name}:T1",
            "weight": 1.0,
        }
        yield "symmetric", {
            "_from": f"topology/{self.name}:P2",
            "_to": f"topology/{self.name}:T1",
            "weight": 1.0,
        }
        yield "symmetric", {
            "_from": f"topology/{self.name}:P1",
            "_to": f"topology/{self.name}:P2",
            "weight": 1.0,
        }

        yield "symmetric", {
            "_from": f"topology/{self.name}:T1",
            "_to": f"topology/{self.name}:T2",
            "weight": 1.0,
        }

        yield "symmetric", {
            "_from": f"topology/{self.name}:P3",
            "_to": f"topology/{self.name}:T2",
            "weight": 1.0,
        }
        yield "symmetric", {
            "_from": f"topology/{self.name}:P4",
            "_to": f"topology/{self.name}:T2",
            "weight": 1.0,
        }
        yield "symmetric", {
            "_from": f"topology/{self.name}:P3",
            "_to": f"topology/{self.name}:P4",
            "weight": 1.0,
        }

        if self.p1:
            yield "symmetric", {
                "_from": f"topology/{self.name}:P1",
                "_to": f"topology/{self.p1}",
                "weight": 1.0,
            }
        if self.p2:
            yield "symmetric", {
                "_from": f"topology/{self.name}:P2",
                "_to": f"topology/{self.p2}",
                "weight": 1.0,
            }
        if self.p3:
            yield "symmetric", {
                "_from": f"topology/{self.name}:P3",
                "_to": f"topology/{self.p3}",
                "weight": 1.0,
            }
        if self.p4:
            yield "symmetric", {
                "_from": f"topology/{self.name}:P4",
                "_to": f"topology/{self.p4}",
                "weight": 1.0,
            }


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

for agent in AGENTS:
    # print("===", agent.name, "=" * (75 - len(agent.name)))  # noqa
    for collection, node in agent.nodes():
        db.collection(collection).insert(node)

    for collection, edge in agent.edges():
        db.collection(collection).insert(edge)

        if collection == "symmetric":
            node = edge["_to"].split("/")[1].split(":")[0]
            if node == agent.name:
                continue
            data = db.collection('agent').get({"_key": node})
            if data is None:
                continue
            data["update"] = True
            db.collection('agent').update(data)

    for data in db.collection('agent').find({"update": True}):

        # print(data["_id"], "-" * (79 - len(data["_id"])))  # noqa

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
        for i in db.aql.execute(query):
            if i is None:
                update = True
                continue
            nodes[i["_id"]] = i

        # skip logical and virtual connected nodes
        for edge in db.collection("logical").find({"_from": data["_id"]}):
            if edge["_to"] in nodes:
                nodes.pop(edge["_to"])
        for edge in db.collection("virtual").find({"_from": data["_id"]}):
            if edge["_to"] in nodes:
                nodes.pop(edge["_to"])

        # add new nodes
        for node in nodes.values():
            if "pool" in data or "pool" in node:
                collection = "virtual"
            else:
                collection = "logical"

            db.collection(collection).insert({
                "_from": data["_id"],
                "_to": node["_id"],
            })

        # update if fully loaded
        if data["update"] != update:
            data["update"] = update
            db.collection('agent').update(data)

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
            for i, p in enumerate(db.aql.execute(query)):
                if i == 0:
                    pool = p
                    continue

                for edge in db.collection('logical').find({"_from": p["_id"]}):
                    edge["_from"] = pool['_id']
                    db.collection('logical').update(edge)

                for edge in db.collection('logical').find({"_to": p["_id"]}):
                    edge["_to"] = pool['_id']
                    db.collection('logical').update(edge)

                db.collection('pool').delete(p)

            if pool is None:
                pool = db.collection("pool").insert({"cls": data["pool"]})

            edges = list(db.collection('logical').find({"_from": pool["_id"], "_to": data["_id"]}))
            if len(edges) == 0:
                db.collection('logical').insert({
                    "_from": pool["_id"],
                    "_to": data["_id"],
                })
            edges = list(db.collection('logical').find({"_to": pool["_id"], "_from": data["_id"]}))
            if len(edges) == 0:
                db.collection('logical').insert({
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
            for node in db.aql.execute(query):
                edges = list(db.collection('logical').find({"_from": pool["_id"], "_to": node["_id"]}))
                if len(edges) == 0:
                    db.collection('logical').insert({
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
            for node in db.aql.execute(query):
                edges = list(db.collection('logical').find({"_to": pool["_id"], "_from": node["_id"]}))
                if len(edges) == 0:
                    db.collection('logical').insert({
                        "_to": pool["_id"],
                        "_from": node["_id"],
                    })

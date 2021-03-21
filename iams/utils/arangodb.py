#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import hashlib

from arango import ArangoClient
from arango import AQLQueryExecuteError


logger = logging.getLogger(__name__)


def get_credentials(namespace, password=None):

    if password is None:
        # TODO make this configurable
        # (specify environment variables or settings to make this configurable)
        with open('/run/secrets/arango', 'r') as f:
            password = f.read().strip()

    database = "iams_" + namespace
    return database, password, hashlib.pbkdf2_hmac("sha1", database.encode(), password.encode(), 10000).hex()[:32]


class Arango(object):

    def __init__(self,
                 namespace=None, username="root", password=None,
                 database=None,
                 hosts="http://tasks.arangodb:8529", docker=None):

        # namespace is set by AMS or left as None by agents
        logger.debug("Init: %s(%s, %s, %s, %s)", self.__class__.__qualname__, namespace, username, password, database)

        self.docker = docker

        if namespace is not None:
            self.agent_username, password, self.agent_password = get_credentials(namespace, password)
            database = self.agent_username
        else:
            self.agent_username = username
            self.agent_password = password

        client = ArangoClient(hosts=hosts)

        # create database and user and password
        if username == "root":
            db = client.db("_system", username=username, password=password, verify=True)
            if not db.has_database(database):
                logger.info("Create Database: %s", database)
                db.create_database(database)

            if db.has_user(database):
                logger.debug("Update user: %s:%s", self.agent_username, self.agent_password)
                db.update_user(
                    username=self.agent_username,
                    password=self.agent_password,
                    active=True,
                )
            else:
                logger.debug("Create user: %s:%s", self.agent_username, self.agent_password)
                db.create_user(
                    username=self.agent_username,
                    password=self.agent_password,
                    active=True,
                )

            # TODO - potential security risk: all agents get access to database ... restrict to read-only?
            logger.debug("Set Permissions to read-only for user %s on database %s", self.agent_username, database)
            db.update_permission(username=self.agent_username, permission="ro", database=database)
        elif namespace is not None:
            raise NotImplementedError("Currently ArangoDB needs to be accessed as root by IAMS")

        # setup database
        self.db = client.db(database, username=username, password=password, verify=True)

        # setup collections - if instance is initialized by IAMS
        if namespace is not None:
            for collection in ["topology", "agent"]:
                if not self.db.has_collection(collection):
                    logger.debug("Create collection %s", collection)
                    self.db.create_collection(collection)

            for edge in ["directed", "symmetric", "logical", "virtual"]:
                if not self.db.has_collection(edge):
                    logger.debug("Create edge %s", edge)
                    self.db.create_collection(edge, edge=True)

            # setup graphs
            if not self.db.has_graph('plants'):
                logger.debug("Create graph: plants")

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
                logger.debug("Create graph: connections")
                self.db.create_graph('connections', edge_definitions=[{
                    "edge_collection": "logical",
                    "from_vertex_collections": ["agent"],
                    "to_vertex_collections": ["agent"],
                }])

            if not self.db.has_graph('all_connections'):
                logger.debug("Create graph: all_connections")
                self.db.create_graph('all_connections', edge_definitions=[{
                    "edge_collection": "logical",
                    "from_vertex_collections": ["agent"],
                    "to_vertex_collections": ["agent"],
                }, {
                    "edge_collection": "virtual",
                    "from_vertex_collections": ["agent"],
                    "to_vertex_collections": ["agent"],
                }])

    def create_agent(self, name, node):

        data = {
            "_key": name,
            "update": True,
            "abilities": list(node.abilities),
        }

        # TODO support resources to be in multiple pools
        if node.pools:
            data["pool"] = node.pools[0]

        logger.debug("adding agent %s with %s", name, data)

        self.db.collection("agent").insert(data)

        self.db.collection("topology").insert({
            "_key": f"{name}:{node.default}",
            "agent": f"agent/{name}",
            "default": True,
        })
        nodes = [node.default]

        for edge in node.edges:

            # agent = edge.agent or name
            if edge.node_from not in nodes:
                self.db.collection("topology").insert({
                    "_key": f"{name}:{edge.node_from}",
                    "agent": f"agent/{name}",
                    "default": False,
                })
                nodes.append(edge.node_from)

            if edge.node_to not in nodes and edge.agent is None:
                self.db.collection("topology").insert({
                    "_key": f"{name}:{edge.node_to}",
                    "agent": f"agent/{name}",
                    "default": False,
                })
                nodes.append(edge.node_to)

            if edge.symmetric:
                collection = "symmetric"
            else:
                collection = "directed"

            if edge.agent:
                self.db.collection(collection).insert({
                    "_from": f"topology/{name}:{edge.node_from}",
                    "_to": f"topology/{edge.agent}:{edge.node_to}",
                    "weight": edge.weight,
                })

                # agent instance connected to this node needs to be updated
                if collection == "symmetric":
                    data = self.db.collection('agent').get({"_key": edge.agent})
                    if data is None:
                        continue
                    logger.info("set update on %s", node)
                    data["update"] = True
                    self.db.collection('agent').update(data)

            else:
                self.db.collection(collection).insert({
                    "_from": f"topology/{name}:{edge.node_from}",
                    "_to": f"topology/{name}:{edge.node_to}",
                    "weight": edge.weight,
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
        self.db.aql.execute(query1, bind_vars={"agent": f"agent/{name}"})
        self.db.aql.execute(query2, bind_vars={"agent": f"agent/{name}"})
        if update:
            self.update_agents()
        return True

    def update_agent(self, name, node):
        try:
            self.delete_agent(name, update=False)
        except AQLQueryExecuteError:
            pass
        self.create_agent(name, node)

    def update_agents(self):
        """
        iterates over all agents with update == true and updates their data
        """
        for data in self.db.collection('agent').find({"update": True}):
            # get neighbor agents
            pk = data["_id"]

            # TODO use template system from arangodb
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

                # TODO use template sysetm from arangodb
                query = f"""
                WITH logical, virtual
                FOR v, e IN 1..100 INBOUND '{pk}' logical, virtual
                    PRUNE v.pool != '{pool}'
                    OPTIONS {{bfs: true, uniqueVertices: 'global'}}
                    FILTER v.pool_cls == '{pool}'
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

                    self.db.collection('agent').delete(p)
                    # TODO delete pool agent - if docker is available

                if pool is None:
                    p = self.db.collection("agent").insert({})
                    pool = self.db.collection("agent").insert({
                        "_key": "pool-%s" % p["_key"],
                        "pool_cls": data["pool"],
                        "color": "#444444",
                    })
                    self.db.collection("agent").delete(p)
                    # TODO create pool agent - if docker is available

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

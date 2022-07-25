Industrial Agent Management System
==================================

Agent-management system designed for industrial applications.
This repository represents a scalable solution for orchestration and deployment of industrial agents.
It follows the hybrid integration patterns for industrial agents and concists of a server part and client libraries that are used to develop clients.

IAMS Server
-----------

The server needs docker swarm available (on premise) and orchestrates mircoservice applications (the agents) in the cluster.
It used docker images, which can be globally distributed by vendors, to deploy a service managing every machine on the shop floor.
Furthermore, it provides provisioning capabilities, allowing the agents to consume cloud-wide services, like log aggregation or databases.
The agents can request the provisioning via docker labels attached to the image.
The IAMS server will generate neccecary configurations and credentials and provide the agents with the access.

The IAMS server runs with a mandatory certificate authority (CFSSL), which is used to provide every agent with its own client certificate.
All internal cloud communication can be encrypted automatically, and agents could use a access control lists (ACLs) to verify requests.
The idea is to use a graph database (arango-db) to store relationships between agents and use them as ACLs, however an example configuration and implementation is not yet provided.

IAMS Clients
------------

Clients use gRPC for their internal communications. gRPC has some advantages in comparision to OPC-UA - it uses TLS, which ensures smaller response times for persistent connections (after the handshake), and it supports Server Name Indication (SNI) which enables the usage of 3rd party proxy servers (nginx, envoy) to securely expose the service to external applications.

As gRPC is used, the client programming language can be specified by the developing team. However, this project only focusses on python as a programming language and provides only for this lanuage a client implementation and libraries that help developing clients.

Typically an agents connects via a TCP-based communication (OPC-UA, HTTP, Sockets) to a machine and used the machine-specific communication protocol to receive staus updates from the machine.
The status updates are processed by the agent, which then updates it's connected agents with it's changed state.
In addition to agents, that are connected to a physical devices, coordination agents can be used to aggregate and group agents.

Example implementations can be found in the "examples" folder of this repository

Contributions
--------------

Feel free to contribute to this repository.

Use the ``Makefile``to generate a docker image. The build process includes basic software tests.

Help and Support
-----------------

Use github tickes for support.

About
============

Mutliagent-System for controlling and simulation of assets in an industrial environment.
Agents represent resources and have interfaces to interact with each other and, if available, with the resource that they
are representing. 
A secure multi-agent-based nonlinear network can be achieved with the utilization of a CA in combination with a coorinated agent network.
With security in mind, the administration and configuration of the agents is reduced to a minimum while keeping a high standard of encryption and security throughout the whole network.
Communication is based on gRPC. Machines can be on isolated networks and thus save from external attacks.
Bases upton docker, gRPC, and is written mainly in python. Agents are supported to be written in python, but can be implemented in all programming languages supported by gRPC
(the only problem is the client authorisation via certificates, where the AMS currently manipulates the certificate CN-value, which might generate some issues for implementations in different languages.

Security concept see "unpublished"

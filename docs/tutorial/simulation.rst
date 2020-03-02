Simulation
------------

The Folder examples/simulation/ gives an example of a simulation.

scenario:

multiple sources generating material, which need to be transported to sinks, where they are consumed

* simulation_pb2_grpc.py
* simulation.proto
* simulation_pb2.py

gRPC interface specification and automatically generated code

* Dockerfile_source
* Dockerfile_sink
* Dockerfile_vehicle

Dockerfiles to create images for source, sink and vehicle

* simulation.yaml

configuration file which starts the simulation

* source.py
* sink.py
* vehicle.py

Agent source codes

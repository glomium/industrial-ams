Installation
============

docker
--------------------

Make sure docker is installed and functioning

https://docs.docker.com/install/

docker swarm
--------------------

> docker swarm init --advertise-addr <MANAGER-IP>

Creates the swarm manager on your PC. A one-node swarm is enough to evaluate industrial-ams. For the installation of docker swarm on multiple nodes, please visit the official docker swarm documentation

https://docs.docker.com/engine/swarm/swarm-tutorial/

cfssl as Certificate Authority
-------------------------------

All communication in our network is encrypted and peer communication is secured with TLS. A Certificate Authority (CA) is used to generate client certificated when they are needed. Docker-secret system is used
to distribute the required certificates and private keys to the agents. To automate certificate generation and distribution CFSSL is used as a CA. The CA needs to be referenced when the AMS starts.

In the demonstration we use the docker-image from https://github.com/glomium/cfssl/blob/master/Dockerfile and start CFSSL togeher with the AMS.

Start as demonstration
-------------------------------

To start the AMS in the local installation, you need to build docker images and deploy the stack. Checkout the git repository and run either

> make build start

or

> docker build -t iams:local .
> docker stack deploy -c docker-compose.yaml iams

This boots up the AMS in control- and simulation mode as well as the CA.

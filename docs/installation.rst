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

cfssl as certificate authority
-------------------------------



* cfssl is required
* runs completely in docker
* fast track: use docker-compose.yaml as template and start all services

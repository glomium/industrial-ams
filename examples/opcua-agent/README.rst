Create a simple OPC-UA agent
============================

Preparation
-----------

* Work on a Linux machine
* Have docker installed

Dockerfile
-----------

Copy the ``Dockerfile`` as a template. It includes a setup routine to install the required libraries via pip and sets labels.
The label ``LABEL iams.services.agent=true`` is set to indicate to the AMS that this image contains an agent.
The build copies a file called ``run.py`` into the working directory and sets the entrypoint to start this file with python.
This file contains the agent's source-code.
For our example, OPC-UA (``asyncua``) and influxdb (``influxdb``) are installed together with the latest release of ``iams``. Both libraries are used in the example.

Build the docker-image with ``docker build -t opcuaagent:latest .`` - the build also works with an empty ``run.py``,
However, every change in your agents requires the build step to be repeated.

Agent-Source
------------

You create a subscription to two variables ``sensor1`` and ``sensor2`` on an OPC-UA server and save both variables (if they change) to a database. 
The example code (see ``run.py``) is explained here.

Imports
~~~~~~~

``from iams.agent import Agent`` is the base class for agents. It contains the interactions with the IAMS-Server and provides a basic programm structure.

``from iams.aio.opcua import OPCUAMixin`` extends the agent with OPC-UA functionality. It adds functions and callbacks to the agent, making it easy to connect to OPC-UA-Servers

``from iams.aio.influx import InfluxMixin`` extends the agent with InfluxDB functionality. It adds functions making it easy to store information in the database.

Preparation of the class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Four attributes are used to store the sensor values and the corresponding OPC-UA nodes.
These attributes are specified in a ``__init__`` function.


Initializing the OPC-UA connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The connection to the OPC-UA server is created automatically.
A call to ``opcua_kwargs`` is used to select the configuration options for OPC-UA.
The Hostname is usually configured by the IAMS-Server.
If the OPC-UA server is not running on the default port, this can be used to set a different port.
Additionally, a ``session_timeout`` is specified in our example.

After the client is connected to the OPC-UA server the ``opcua_start`` callback is used to establish the subscriptions and store the OPC-UA nodes in the instance.

The OPC-UA client is checking the connection, according to the time specified ``session_timeout``.
However, the subscriptions can be stopped by the server. Thus it is helpful to subscribe to ``i=2258`` (Server_ServerStatus_CurrentTime) and observe if the subscription needs to be renewed.


Getting data changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every time a new value is received, the ``opcua_datachange`` callback is called.
We use the callback to identify the node, change it's value and emit a debug message.

The responses from the ``opcua_datachange`` callback are collected and a second callback ``opcua_datachanges`` is called automatically.
There can be many datachanges in one OPC-UA update request and this callback is called once per update request.
So it's ideal place to store data in the database by preparing the data and calling ``influxdb_write``.


Finally
-------

The created agent-image needs to be made available to the IAMS-Server.
This can be done by exporting the image (``docker image save`` and ``docker image load``) or by uploading (see https://docs.docker.com/docker-hub/) the image to a image-repository that is reachable by the IAMS-Server.


Additional reading
------------------

Currently it's recommended to read the source-code of the industrial-ams libraray or look at example configurations.

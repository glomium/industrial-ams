Create a simple OPC-UA agent
============================

Preparation
-----------

* Work on a Linux machine
* Have docker installed
* Have make installed
* Clone or copy the industrial-ams repository
* Create an docker image for industrial-ams with the command ``make build`` running from the root directory of the repository. This docker image is called ``iams:local``.

Dockerfile
-----------

From now on you can work in a new directory somewhere on your system.

Create a ``Dockerfile``. This file contains a ``FROM iams:local`` indicating the docker image which is used as a template for your agent.
You also need one ``LABEL iams.services.agent=true`` to indicat to the AMS that this image contains an agent.
Now you need create a file ``run.py`` which needs to be copied in the build-process by ``COPY run.py ./run.py``.
This file contains the agent's source-code. It needs to be called by docker, which is done by adding the following line ``ENTRYPOINT ["/usr/bin/python3", "run.py"]`` to ``Dockerfile``.
Additionally, the OPC-UA (``asyncua 0.9.94``) needs to be installed. This is done by a ``RUN pip install asyncua==0.9.94``

Now a minimalistic ``Dockerfile`` is created. In our use-case we want to connect to a OPC-UA device and dump variables into a timeseries database.
We use InfluxDB as this database and assume that the IAMS-Server is configured correctly.
Thus, you only need to add a label ``LABEL iams.plugins.influxdb=MySensor`` to you ``Dockerfile`` and install ``influxdb==5.3.1`` via pip (add it to the specified install command).

Build the docker-image with ``docker build -t opcuaagent:latest .`` - it also works with an empty ``run.py``,
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
In our example-code a ``session_timeout`` is specified.

After the client is connected to the OPC-UA server the ``opcua_start`` callback is used to establish the subscriptions and store the OPC-UA nodes in the instance.

The OPC-UA server should send keep-alive signals, according to the time specified by ``session_timeout``.
However, some implementations don't send this signal. To detect a disconnect, you can send a update-request from the client.
Use the ``opcua_keepalive`` callback for this.


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

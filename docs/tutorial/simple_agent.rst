Simple Agent
------------

The simplest agent inherits from Agent. It only needs to implement a _loop function. The Agent can then be initialized. This
instance is callable and needs to be called, when the programm should start. The instance is not called after the 
initialization, because of unit testing.

.. literalinclude:: ../../examples/simple_agent/run.py
   :language: python
   :linenos:

self._stop_event is an event object from the python threading library. Is is set, when the agent is supposed to shutdown.
The next thing is to create a docker image. This is done with this Dockerfile

.. literalinclude:: ../../examples/simple_agent/Dockerfile
   :linenos:

and by executing

> docker build .

Image can be tagged and uploaded to a registry, which is reachable by the AMS.
Images without the label "iams.service.agent=true" won't be accepted by the AMS. Make sure to add this line to your
Dockerfile or in the docker image build process.

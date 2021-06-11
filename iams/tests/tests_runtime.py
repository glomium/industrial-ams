#!/usr/bin/python
# ex:set fileencoding=utf-8:
"""
unittests for iams.runtime
"""
# pylint: disable=missing-function-docstring,missing-class-docstring,protected-access

import unittest

from iams.tests.ca import CA
from iams.exceptions import InvalidAgentName
from iams.proto import framework_pb2

try:
    import docker

    from iams.runtime import DockerSwarmRuntime

    try:
        # create and connect client
        client = docker.DockerClient()
        # test if docker-client allowed to call the nodes list
        # and thus is a manager and can create services
        client.nodes.list(filters={'role': 'manager'})
        try:
            client.images.get("busybox:latest")
        except docker.errors.ImageNotFound:  # pragma: no cover
            client.images.pull("busybox:latest")

    except Exception:  # pragma: no cover
        SKIP = True
    else:
        SKIP = False

except ImportError:  # pragma: no cover
    SKIP = True


@unittest.skipIf(SKIP, "DockerSwarm is not configured propperly")
class DockerSwarmRuntimeTests(unittest.TestCase):

    def setUp(self):
        self.instance = DockerSwarmRuntime(CA())
        self.instance.client = client
        self.instance.namespace = "iams-unittest"
        self.instance.iams_namespace = "iut"
        self.instance()

    def test_get_valid_agent_name(self):
        valid_names = [("iut_test1", "iut_test1"), ("test-1", "iut_test-1")]
        invalid_names = ["iut_1test", "other_test1"]
        for name, result in valid_names:
            with self.subTest("valid", name=name):
                response = self.instance.get_valid_agent_name(name)
                self.assertEqual(response, result)

        for name in invalid_names:
            with self.subTest("invalid", name=name):
                with self.assertRaises(InvalidAgentName):
                    self.instance.get_valid_agent_name(name)

    @unittest.expectedFailure
    def test_get_service_and_name(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_get_agent_plugins(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_get_agent_config(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_wake_agent(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_sleep_agent(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_delete_agent(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_delete_agent_secrets(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_delete_agent_configs(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_get_service(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_get_image_version(self):
        raise NotImplementedError

    def test_agent_create_update_delete(self):
        # delete (in case an error ocured earlier)
        try:
            self.instance.delete_agent("doesnotexist")
        except docker.errors.NotFound:
            pass

        # create
        request = framework_pb2.AgentData(
            name="doesnotexist",
            image="busybox",
            version="latest",
            address="localhost",
            port=5555,
            autostart=False,
        )
        self.instance.update_agent(request, create=True, skip_label_test=True)

        # update
        request = framework_pb2.AgentData(
            name="doesnotexist",
            image="busybox",
            version="latest",
            autostart=False,
        )
        self.instance.update_agent(request, skip_label_test=True)

        # update
        request = framework_pb2.AgentData(
            name="doesnotexist",
            image="busybox",
            version="latest",
            address="localhost",
            port=5555,
            autostart=False,
        )
        self.instance.update_agent(request, skip_label_test=True)

        # delete
        self.instance.delete_agent("doesnotexist")

    def test_image_has_no_label(self):
        request = framework_pb2.AgentData(
            name="doesnotexist",
            image="busybox",
            version="latest",
        )
        with self.assertRaises(docker.errors.ImageNotFound):
            self.instance.update_agent(request, create=True)

    def test_update_and_create_set(self):
        request = framework_pb2.AgentData(name="doesnotexist")
        with self.assertRaises(ValueError):
            self.instance.update_agent(request, create=True, update=True)

    def test_agent_no_image_or_version(self):
        request = framework_pb2.AgentData(name="doesnotexist")
        with self.assertRaises(ValueError):
            self.instance.update_agent(request)

    @unittest.expectedFailure
    def test_set_secret(self):
        raise NotImplementedError

    @unittest.expectedFailure
    def test_set_config(self):
        raise NotImplementedError

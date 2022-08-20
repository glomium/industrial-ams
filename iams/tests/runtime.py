#!/usr/bin/python3
# vim: set fileencoding=utf-8 :
"""
test runtime
"""
# pylint: disable=empty-docstring


from iams.interfaces.runtime import RuntimeInterface


class Runtime(RuntimeInterface):
    """
    """

    def __call__(self) -> None:
        """
        """

    @staticmethod
    def get_address():  # pylint: disable=arguments-differ
        """
        """
        return ("localhost", 0)

    @staticmethod
    def get_namespace():  # pylint: disable=arguments-differ
        return "unittest"

    def get_valid_agent_name(self, name):
        """
        """

    def get_agent_plugins(self, name):
        """
        """

    def get_agent_config(self, name):
        """
        """

    def get_expired(self):
        """
        """

    def wake_agent(self, name):
        """
        """

    def sleep_agent(self, name):
        """
        """

    def delete_agent(self, name):
        """
        """

    def delete_agent_secrets(self, name):
        """
        """

    def delete_agent_configs(self, name):
        """
        """

    def update_agent(self, request, create=False, update=False):
        """
        """

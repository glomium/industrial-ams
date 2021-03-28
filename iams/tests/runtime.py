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

    def get_valid_agent_name(self, name):
        """
        """

    def get_agent_plugins(self, name):
        """
        """

    def get_agent_config(self, name):
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

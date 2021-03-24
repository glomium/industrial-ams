#!/usr/bin/python3
# vim: set fileencoding=utf-8 :


from iams.interfaces.runtime import RuntimeInterface


class Runtime(RuntimeInterface):

    def __init__(self) -> None:
        super().__init__()

    def __call__(self) -> None:
        pass

    def get_valid_agent_name(self, name):
        pass

    def get_agent_plugins(self, name):
        pass

    def get_agent_config(self, name):
        pass

    def wake_agent(self, name):
        pass

    def sleep_agent(self, name):
        pass

    def delete_agent(self, name):
        pass

    def delete_agent_secrets(self, name):
        pass

    def delete_agent_configs(self, name):
        pass

    def update_agent(self, request, create=False, update=False):
        pass

#!/usr/bin/python3
# vim: set fileencoding=utf-8 :


# Plugin validation
class SkipPlugin(AssertionError):
    """
    """
    pass


# Simulation loop
class EventNotFound(StopIteration):
    """
    """
    pass


# Simulation loop
class Continue(Exception):
    """
    """
    pass

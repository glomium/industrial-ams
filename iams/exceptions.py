#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exceptions raised by iams library
"""


class SkipPlugin(AssertionError):
    """
    Raised when an available plugin is not supported by the server
    """


class StopExecution(Exception):
    """
    Raised to stop the threadpool executor in agents
    """


class StopSimulation(Exception):
    """
    Raised if the agent name is not compatible with the runtime
    """


class InvalidAgentName(ValueError):
    """
    Raised if the agent name is not compatible with the runtime
    """


class CanNotSchedule(AssertionError):
    """
    Raised if the scheduler does not find a solution
    """

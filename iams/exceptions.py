#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exceptions raised by iams library
"""


class SkipPlugin(AssertionError):
    """
    Raised when an available plugin is not supported by the server
    """


class InvalidAgentName(ValueError):
    """
    Raised if the agent name is not compatible with the runtime
    """


class CanNotSchedule(AssertionError):
    """
    Raised if the scheduler does not find a solution
    """

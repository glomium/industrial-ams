#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
helper for loading plugins
"""

import logging
import os
import sys
from importlib.util import find_spec
from importlib.util import module_from_spec
from inspect import getmembers, isclass


from iams.interfaces.plugin import Plugin


plugin_name = "plugin"  # pylint: disable=invalid-name
logger = logging.getLogger(__name__)


def get_plugins():
    """
    read plugins from cwd
    """
    specs = []

    # get plugins included in lib
    for obj in os.scandir(os.path.join(os.path.dirname(__file__), "..", "plugins")):
        if not obj.is_dir():
            continue
        spec = find_spec(f".{obj.name}.{plugin_name}", "iams.plugins")
        if spec:
            specs.append(spec)

    # get plugins from working directory
    directory = os.path.abspath(os.path.curdir)
    if directory not in sys.path:
        sys.path.append(directory)
    logger.debug("Scanning %s for plugins", directory)
    for obj in os.scandir(directory):
        if not obj.is_dir() or obj.name[0] == ".":
            continue

        try:
            spec = find_spec(f"{obj.name}.{plugin_name}")
        except ModuleNotFoundError:
            continue

        if spec:
            logger.debug("Found plugin in module %s", obj.name)
            specs.append(spec)

    # get plugins from specs
    for spec in specs:
        try:
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
        except ModuleNotFoundError:
            logger.exception("Import error for %s", spec.name)
            continue

        for name, cls in getmembers(module, isclass):  # pylint: disable=unused-variable
            if cls is not Plugin and issubclass(cls, Plugin):
                yield cls


if __name__ == "__main__":  # pragma: no cover
    print("Plugins:")  # noqa
    for plugin in get_plugins():
        print(plugin)  # noqa

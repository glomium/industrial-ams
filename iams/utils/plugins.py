#!/usr/bin/python
# ex:set fileencoding=utf-8:

import logging
import os

from importlib.util import find_spec
from inspect import getmembers, isclass


from ..interface import Plugin


plugin_name = "plugin"
logger = logging.getLogger(__name__)


def get_plugins():
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
    logger.debug("Scanning %s for plugins", directory)
    for obj in os.scandir(directory):
        if not obj.is_dir():
            continue
        try:
            spec = find_spec(f".{plugin_name}", f"{obj.name}")
        except ModuleNotFoundError:
            continue
        if spec:
            logger.debug("Found plugin in module %s", obj.name)
            specs.append(spec)

    # get plugins from specs
    for spec in specs:
        try:
            module = spec.loader.load_module()
        except ModuleNotFoundError:
            logger.exception("Import error for %s" % spec.name)
            continue

        for name, cls in getmembers(module, isclass):
            if cls is not Plugin and issubclass(cls, Plugin):
                yield cls


if __name__ == "__main__":
    print("Plugins:")  # noqa
    for plugin in get_plugins():
        print(plugin)  # noqa

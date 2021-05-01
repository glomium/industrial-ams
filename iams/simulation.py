#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-locals

"""
Manages simulation configurations
"""

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from importlib import import_module
from itertools import product
from logging.config import dictConfig
from math import floor
from math import log10

import argparse
import logging
import os
import yaml

try:
    # try to import sentry so that it can be used to log errors
    import sentry_sdk  # noqa
    SENTRY = True
except ImportError:
    SENTRY = False

# from iams.interfaces.df import DirectoryFacilitatorInterface

from iams.interfaces.simulation import SimulationInterface
from iams.tests.df import DF


logger = logging.getLogger(__name__)


def process_config(path, config, dryrun=False, force=False, loglevel=logging.WARNING, dsn=None):  # pylint: disable=too-many-arguments  # noqa: E501
    """
    processes a simulation config
    """
    path = os.path.abspath(path)
    folder = os.path.join(os.path.dirname(path), config.get("foldername", "results"))
    project = os.path.basename(path)[:-5]

    if not SENTRY:
        dsn = None

    if not dryrun and not os.path.exists(folder):
        os.mkdir(folder)

    products = []
    length = 1
    for key, values in config.get("products", {}).items():
        length *= len(values)
        data = []
        for value in values:
            data.append((key, value))
        products.append(data)

    if length > 1:
        length = int(floor(log10(length)) + 1)
        try:
            template = project + '-' + config['formatter']
        except KeyError:
            template = project + '-{:0%dd}' % length
    else:
        template = project

    count = 0
    for run_config in product(*products):
        run_config = dict(run_config)
        count += 1

        kwargs = prepare_run(count, folder, template, run_config, config.copy())

        if not dryrun and not force and os.path.exists(kwargs['file_data']):  # pragma: no cover
            continue

        if dryrun:
            kwargs['file_data'] = None

        log_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': "%(levelname)s %(message)s",
                },
                'logfile': {
                    'format': "%(message)s",
                },
                'debug': {
                    'format': "%(levelname)s [%(name)s:%(lineno)s] %(message)s",
                },
            },
            'handlers': {
                'console': {
                    'class': "logging.StreamHandler",
                    'level': loglevel,
                    'formatter': 'debug' if loglevel < logging.INFO else "default",
                },
                'file': {
                    'class': "logging.FileHandler",
                    'level': logging.DEBUG if loglevel < logging.INFO else logging.INFO,
                    'formatter': 'debug' if loglevel < logging.INFO else "logfile",
                    'filename': kwargs.pop("file_log"),
                    'mode': 'w',
                },
            },
            'root': {
                'handlers': ['console'],
                'level': logging.DEBUG if loglevel < logging.INFO else logging.INFO,
            },
        }
        if dryrun is True:
            del log_config['handlers']['file']
        else:
            log_config['root']['handlers'].append('file')
            log_config['handlers']['console']['level'] = logging.WARNING
            log_config['handlers']['console']['formatter'] = "logfile"
        kwargs.update({'log_config': log_config, 'dryrun': dryrun, 'dsn': dsn})

        yield kwargs


def prepare_run(count, folder, template, run_config, config):
    """
    prepare a single run
    """
    name = template.format(count, **run_config)
    seed = config.get('seed', name).format(count, **run_config)
    start = config.get('start', 0)
    stop = config.get('stop', None)

    try:
        module_name, class_name = config["simulation-class"].rsplit('.', 1)
    except (KeyError, AttributeError) as exception:
        raise ValueError('The configuration-file needs a valid "simulation-class-setting') from exception
    else:
        simcls = getattr(import_module(module_name), class_name)

        if not issubclass(simcls, SimulationInterface):
            raise AssertionError(f"{simcls.__qualname__} needs to be a subclass of {SimulationInterface.__qualname__}")

    try:
        module_name, class_name = config["directory-facilitator"].rsplit('.', 1)
    except (KeyError, AttributeError):
        df = DF()  # pylint: disable=invalid-name
    else:
        raise NotImplementedError("the directory facilitator cannot be changed")
        # df = getattr(import_module(module_name), class_name)
        # if not issubclass(df, DierctoryFacilitatorInterface):
        #     raise TypeError(
        #         "%s needs to be a subclass of %s",
        #         df.__qualname__,
        #         DirectoryFacilitatorInterface.__qualname__,
        #     )

    settings = config.get('settings', {})
    settings.update(run_config)

    for key in [
        "formatter",
        "simulation-class",
        "directory-facilitator",
        "products",
        "seed",
        "settings",
        "start",
        "stop",
    ]:
        try:
            del config[key]
        except KeyError:
            pass

    return {
        'config': config,
        'df': df,
        'file_data': os.path.join(folder, name + '.dat'),
        'file_log': os.path.join(folder, name + '.log'),
        'folder': folder,
        'name': name,
        'seed': seed,
        'settings': settings,
        'simcls': simcls,
        'start': start,
        'stop': stop,
    }


def load_agent(agents, global_settings):
    """
    generate agents from configuration
    """
    for agent in agents:
        module_name, class_name = agent["class"].rsplit('.', 1)
        cls = getattr(import_module(module_name), class_name)
        settings = agent.get('settings', {})
        for name in agent.get('use_global', []):
            settings[name] = global_settings[name]

        products = []
        for key, values in agent.get("products", {}).items():
            data = []
            for value in values:
                data.append((key, value))
            products.append(sorted(data))

        for prod in product(*products):
            settings.update(dict(prod))
            logger.debug("Create agent: %r with %s", cls, settings)
            try:
                instance = cls(**settings)
            except TypeError as exception:
                raise TypeError('%s on %r' % (exception, cls)) from exception
            logger.info("Created agent: %s", instance)
            yield instance


def run_simulation(  # pylint: disable=invalid-name,too-many-arguments
        simcls, df, name, folder, settings, start, stop, seed, config,
        dryrun, log_config, file_data, dsn):
    """
    execute single simulation config
    """
    dictConfig(log_config)
    if dsn:
        logger.warning('Using sentry DSN %s', dsn)
        sentry_sdk.init(dsn)
    logger.warning('Start simulation "%s"', name)

    with open(file_data or os.devnull, "w") as fobj:
        # init simulation
        simulation = simcls(
            df=df,
            name=name,
            folder=folder,
            fobj=fobj,
            start=start,
            stop=stop,
            seed=seed,
        )

        for agent in load_agent(config.get('agents', []), settings):
            simulation.register(agent)

        # run simulation
        simulation(dryrun, settings)


def parse_command_line(argv=None):
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-q', '--quiet',
        action="store_const",
        const=logging.WARNING,
        default=logging.INFO,
        dest="loglevel",
        help="Be quiet",
    )
    parser.add_argument(
        '-d', '--debug',
        action="store_const",
        const=logging.DEBUG,
        dest="loglevel",
        help="Debugging statements",
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        default=False,
        dest="force",
        help="Allow overwriting of existing runs",
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        dest="dryrun",
        help="Dry-run",
    )
    parser.add_argument(
        '--single',
        action='store_true',
        default=False,
        dest="single",
        help="Only run one instance",
    )
    parser.add_argument(
        '--dsn',
        default=None,
        dest="dsn",
        help="Sentry DSN",
    )
    parser.add_argument(
        'configs',
        nargs='+',
        help="Simulation configuration files",
        type=argparse.FileType('r'),
    )
    return parser.parse_args(argv)


def main(args, function=run_simulation):
    """
    main function
    """
    kwarg_list = []
    for fobj in args.configs:
        try:
            assert fobj.name.endswith('.yaml'), "Config needs to be '.yaml' file"
            config = yaml.load(fobj, Loader=yaml.SafeLoader)
            assert isinstance(config, dict), "Config has the wrong format"
        finally:
            fobj.close()

        for kwargs in process_config(
                fobj.name, config, dryrun=args.dryrun,
                force=args.force, loglevel=args.loglevel,
                dsn=args.dsn):
            kwarg_list.append(deepcopy(kwargs))

    if len(kwarg_list) == 1 or args.single:
        function(**kwarg_list.pop(0))
    elif len(kwarg_list) > 1:
        with ProcessPoolExecutor() as executor:
            for kwargs in kwarg_list:
                executor.submit(function, **kwargs).add_done_callback(handler)


def handler(future):
    """
    the responde from the process pool exetutor is catched here
    """
    try:
        future.result()
    except Exception as exception:  # pylint: disable=broad-except
        logger.exception(str(exception))


def execute_command_line():  # pragma: no cover
    """
    Execute command line
    """
    main(parse_command_line())


if __name__ == "__main__":  # pragma: no cover
    main(parse_command_line())

#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import logging
import yaml
import sys
import os

# from logging.config import dictConfig
# from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import wait
from importlib import import_module
from itertools import product
from math import floor
from math import log10


from iams.tests.df import TestDF
from iams.interfaces.simulation import SimulationInterface


logger = logging.getLogger(__name__)


def parse_command_line(argv=None):

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
        'configs',
        nargs='+',
        help="Simulation configuration files",
        type=argparse.FileType('r'),
    )
    return parser.parse_args(argv)


def execute_command_line(args):
    kwarg_list = []
    for fobj in args.configs:
        try:
            assert fobj.name.endswith('.yaml'), "Config needs to be '.yaml' file"
            config = yaml.load(fobj, Loader=yaml.SafeLoader)
            assert isinstance(config, dict), "Config has the wrong format"
        finally:
            fobj.close()

        for kwargs in process_config(fobj.name, config, dryrun=args.dryrun, force=args.force, loglevel=args.loglevel):
            kwarg_list.append(kwargs)

    with ProcessPoolExecutor() as executor:
        futures = []
        while True:
            try:
                futures.append(executor.submit(
                    run_simulation,
                    **kwarg_list.pop(0),
                ))
            except IndexError:
                break

        wait(futures)
        for future in futures:
            future.result()


def process_config(path, config, dryrun=False, force=False, loglevel=logging.WARNING):
    path = os.path.abspath(path)
    folder = os.path.dirname(path)
    project = os.path.basename(path)[:-5]

    permutations = []
    length = 1
    for key, values in config.get("permutations", {}).items():
        length *= len(values)
        data = []
        for value in values:
            data.append((key, value))
        permutations.append(data)

    if length > 1:
        length = int(floor(log10(length)) + 1)
        try:
            template = project + '-' + config['formatter']
        except KeyError:
            template = project + '-{:0%dd}' % length
    else:
        template = project

    count = 0
    for run_config in product(*permutations):
        run_config = dict(run_config)
        count += 1

        kwargs = prepare_run(count, folder, template, run_config, config.copy())

        if not dryrun and not force and os.path.exists(kwargs['file_data']):  # pragma: no cover
            continue

        kwargs.update({'force': force, 'dryrun': dryrun, 'loglevel': loglevel})

        yield kwargs


def prepare_run(count, folder, template, run_config, config):
    name = template.format(count, **run_config)
    log_dir = os.path.join(folder, name + '.log')
    data_dir = os.path.join(folder, name + '.dat')

    seed = config.get('seed', name)
    start = config.get('start', 0)
    stop = config.get('stop', None)

    try:
        module_name, class_name = config["simulation-class"].rsplit('.', 1)
    except (KeyError, AttributeError):
        raise ValueError('The configuration-file needs a valid "simulation-class-setting')
    else:
        simcls = getattr(import_module(module_name), class_name)

        if not issubclass(simcls, SimulationInterface):
            raise AssertionError(
                "%s needs to be a subclass of %s",
                simcls.__qualname__,
                SimulationInterface.__qualname__,
            )

    try:
        module_name, class_name = config["directory-facilitator"].rsplit('.', 1)
    except (KeyError, AttributeError):
        df = TestDF()
    else:
        df = getattr(import_module(module_name), class_name)

        if not issubclass(df, SimulationInterface):
            raise AssertionError(
                "%s needs to be a subclass of %s",
                df.__qualname__,
                SimulationInterface.__qualname__,
            )

    settings = config.get('settings', {})
    settings.update(run_config)

    for x in [
        "formatter",
        "simulation-class",
        "directory-facilitator",
        "permutations",
        "seed",
        "settings",
        "start",
        "stop",
    ]:
        try:
            del config[x]
        except KeyError:
            pass

    return {
        'config': config,
        'df': df,
        'file_data': data_dir,
        'file_log': log_dir,
        'folder': folder,
        'name': name,
        'seed': seed,
        'settings': settings,
        'simcls': simcls,
        'start': start,
        'stop': stop,
    }


def load_agent(agents, global_settings):
    for agent in agents:
        module_name, class_name = agent["class"].rsplit('.', 1)
        cls = getattr(import_module(module_name), class_name)
        settings = agent.get('settings', {})
        for name in agent.get('use_global', []):
            settings[name] = global_settings[name]

        permutations = []
        for key, values in agent.get("permutations", {}).items():
            data = []
            for value in values:
                data.append((key, value))
            permutations.append(sorted(data))

        for permutation in product(*permutations):
            settings.update(dict(permutation))
            logger.debug("Create agent: %r with %s", cls, settings)
            instance = cls(**settings)
            logger.info("Created agent: %s", instance)
            yield instance


def run_simulation(
        simcls, df, name, folder, settings, start, stop, seed, config,
        dryrun, force, loglevel, file_data, file_log):

    if loglevel == logging.DEBUG:
        formatter = "%(levelname).1s [%(name)s:%(lineno)s] %(message)s"
    else:
        formatter = '%(message)s'

    if dryrun:
        file_data = os.devnull  # redirect output to null device
        logging.basicConfig(
            stream=sys.stdout,
            level=loglevel,
            format=formatter,
        )
    else:
        logging.basicConfig(
            filename=file_log,
            filemode='w',
            level=loglevel,
            force=True,
            format=formatter,
        )

    with open(file_data, "w") as fobj:
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


if __name__ == "__main__":  # pragma: no cover
    execute_command_line(parse_command_line())

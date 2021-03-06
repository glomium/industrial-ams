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
        dryrun, force, loglevel, file_data, file_log, **kwargs):

    if loglevel == logging.DEBUG:
        formatter = "%(levelname).1s [%(name)s:%(lineno)s] %(message)s"
    else:
        formatter = '%(message)s'

    # TODO
    print("TODO", kwargs)  # noqa

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


def prepare_data(path, config):
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

    for permutation in product(*permutations):
        yield folder, template, dict(permutation)


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
    futures = []
    with ProcessPoolExecutor() as e:
        for fobj in args.configs:
            try:
                assert fobj.name.endswith('.yaml'), "Configfile needs to be '.yaml' file"
                config = yaml.load(fobj, Loader=yaml.SafeLoader)
            except Exception:
                logger.exception('error loading %s', fobj.name)
                continue

            count = 0
            for folder, template, run_config in prepare_data(fobj.name, config):
                count += 1
                try:
                    kwargs = prepare_run(count, folder, template, run_config, config.copy())
                except (AssertionError, AttributeError, ModuleNotFoundError) as e:
                    logger.exception(str(e))
                    continue

                if not args.dryrun and not args.force and os.path.exists(kwargs['file_data']):
                    continue

                kwargs.update({'force': args.force, 'dryrun': args.dryrun, 'loglevel': args.loglevel})
                futures.append(e.submit(
                    run_simulation,
                    **kwargs,
                ))

        wait(futures)
        for x in futures:
            x.result()


if __name__ == "__main__":  # pragma: no cover
    execute_command_line(parse_command_line())

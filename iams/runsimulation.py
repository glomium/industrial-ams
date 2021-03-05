#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import logging
import yaml
import sys
import os

# from logging.config import dictConfig
from itertools import product
from math import floor
from math import log10

from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import wait
# from logging.config import dictConfig

logger = logging.getLogger(__name__)


def run_simulation(project, folder, config, iteration):
    # logging.basicConfig(filename=r'test_%s.log' % name, filemode='w', level=logging.DEBUG)
    # logging.info('this is sub logging')
    print(project, folder, config, iteration)  # noqa


def execute_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-q', '--quiet',
        help="Be quiet",
        action="store_const",
        dest="loglevel",
        const=logging.WARNING,
        default=logging.INFO,
    )
    parser.add_argument(
        '-d', '--debug',
        help="Debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
    )
    parser.add_argument(
        'configs',
        nargs='+',
        help="Simulation configuration files",
        type=argparse.FileType('r'),
        default=sys.stdin,
    )
    args = parser.parse_args()

    futures = []
    with ProcessPoolExecutor() as e:
        for fobj in args.configs:
            try:
                assert fobj.name.endswith('.yaml'), "file needs to have a yaml extension"
                config = yaml.load(fobj, Loader=yaml.SafeLoader)
            except Exception:
                logger.exception('error loading file %s', fobj.name)
                continue

            path = os.path.abspath(fobj.name)
            folder = os.path.dirname(path)
            project = os.path.basename(path)[:-5]

            iterations = []
            length = 1
            for key, values in config.get("iterations", {}).items():
                length *= len(values)
                data = []
                for value in values:
                    data.append((key, value))
                iterations.append(data)

            if length > 1:
                length = int(floor(log10(length)) + 1)
                template = project + config.get('formatter', '') + '%%0%dd' % length
            else:
                template = project

            count = 0
            for iteration in product(*iterations):
                iteration = dict(iteration)
                count += 1

                if length > 1:
                    name = template.format(**iteration) % count
                else:
                    name = template

                output = os.path.join(folder, name + '.dat')

                if os.path.exists(output):
                    continue

                futures.append(e.submit(
                    run_simulation,
                    name,
                    os.path.join(folder, name),
                    config,
                    iteration,
                ))

        wait(futures)
        for x in futures:
            x.result()


if __name__ == "__main__":
    execute_command_line()

#!/usr/bin/python
# ex:set fileencoding=utf-8:

import argparse
import logging
import yaml
import sys

from logging.config import dictConfig

import grpc

from .helper import get_logging_config
from .proto import simulation_pb2
from .proto import framework_pb2
from .stub import SimulationStub
from .utils.grpc import framework_channel


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
        '-t', '--time',
        help="simulation time",
        type=int,
        dest="time",
    )
    parser.add_argument(
        '-s', '--seed',
        help="random seed",
        dest="seed",
    )
    parser.add_argument(
        'config',
        help="Simulation configuration file",
        type=argparse.FileType('r'),
        default=sys.stdin,
    )

    parser.add_argument(
        'hosts',
        help="gRPC interfaces for simulation runtimes",
        default="127.0.0.1:5115",
        nargs="+",
    )

    args = parser.parse_args()

    dictConfig(get_logging_config(["iams"], args.loglevel))
    logger = logging.getLogger(__name__)

    # load config
    simulation_config = yaml.load(args.config, Loader=yaml.SafeLoader)

    # read agent config
    agents = {}
    for name, data in simulation_config.get("agents", {}).items():
        if "config" in data and data["config"]:
            cfg = yaml.dump(data["config"]).encode()
        else:
            cfg = None

        config = simulation_pb2.AgentConfig(
            container=framework_pb2.AgentData(
                name=name,
                image=data["image"]["name"],
                version=data["image"]["version"],
                autostart=data["image"].get("autostart", True),
                config=cfg,
            ),
        )
        agents[name] = config

    request = simulation_pb2.SimulationConfig(agents=[agents[x] for x in sorted(agents)])

    # update simulation environment
    if args.time:
        request.until = args.time
    elif 'until' in simulation_config:
        request.until = simulation_config["until"]

    if args.seed:
        request.seed = args.seed.encode()
    elif 'seed' in simulation_config:
        if isinstance(simulation_config["seed"], bytes):
            request.seed = simulation_config["seed"]
        elif isinstance(simulation_config["seed"], str):
            request.seed = simulation_config["seed"].encode()
        else:
            request.seed = bytes(str(simulation_config["seed"]).encode())

    logger.debug(request)

    for host in args.hosts:
        server, port = host.split(':')
        port = int(port)
        logger.info("connect to runtime at %s:%s", server, port)

        try:
            with framework_channel(server, port=port, secure=False) as channel:
                stub = SimulationStub(channel)
                for response in stub.start(request):
                    if response.log.ByteSize():
                        logger.info('[%s] %s: %s', response.time, response.name, response.log.text)
                    if response.metric.ByteSize():
                        logger.info('[%s] %s: %s', response.time, response.name, dict(response.metric.metrics))

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                logger.debug("got error message: %s", e.details())
                logger.info("simulation running on %s - try next runtime", server)
                continue
            raise

        break  # dont start a second simulation on a different host


if __name__ == "__main__":
    execute_command_line()

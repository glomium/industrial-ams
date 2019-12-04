#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import re
import os

import grpc

from docker import errors as docker_errors
# from docker.types import Placement
from docker.types import ServiceMode
from google.protobuf.empty_pb2 import Empty

from .proto import simulation_pb2
from .proto import simulation_pb2_grpc
from .proto import framework_pb2
from .proto import framework_pb2_grpc
from .utils import agent_required


logger = logging.getLogger(__name__)


class SimulationServicer(simulation_pb2_grpc.SimulationServicer):

    def __init__(self, parent):
        self.parent = parent

    def test(self, request, context):
        if self.parent.simulation is None:
            message = 'No simulation is currently running'
            context.abort(grpc.StatusCode.NOT_FOUND, message)

    def add_event(self, agent, uuid, delay, allow_next):
        if uuid:
            time, start_next = self.parent.simulation.add_event(agent, uuid, delay)
            logger.debug(
                "%s scheduled a new event with a delay of %s at %s",
                agent,
                delay,
                time,
            )
            return start_next and allow_next, simulation_pb2.EventSchedule(time=time)
        return allow_next, simulation_pb2.EventSchedule()

    @agent_required
    def resume(self, request, context):
        self.test(request, context)
        start_next, response = self.add_event(context._agent, request.uuid, request.delay, True)
        if start_next:
            logger.debug("%s requested the next step", context._agent)
            # resume simulation runtime
            self.parent.simulation.event.set()
        return response

    @agent_required
    def schedule(self, request, context):
        self.test(request, context)
        start_next, response = self.add_event(context._agent, request.uuid, request.delay, False)
        return response


class FrameworkServicer(framework_pb2_grpc.FrameworkServicer):

    def __init__(self, args):
        # def __init__(self, parent, prefix, client):
        self.args = args
        prefix = "sim"
        # self.parent = parent
        # self.prefix = prefix
        # self.client = client
        self.RE_ENV = re.compile(r'^AMS_(ADDRESS|KWARGS)=(.*)$')
        self.RE_NAME = re.compile(r'^(%s_)?([\w]+)$' % prefix[0])

    # Common used functions

    def get_service(self, context, name):
        try:
            return self.client.services.list(filters={'label': ["ams.type=%s" % self.prefix], 'name': name})[0]
        except IndexError:
            message = 'Could not find %s' % name
            context.abort(grpc.StatusCode.NOT_FOUND, message)

    def get_service_data(self, service):
        image, version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].image.rsplit(':', 1)  # noqa
        autostart = service.attrs['Spec']['Labels'].get('ams.autostart', None) == 'True'
        address = None
        config = None
        for env in filter(self.RE_ENV.match, service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Env']):
            name, value = self.RE_ENV.match(env).groups()
            if name == "ADDRESS":
                address = value
            if name == "KWARGS":
                config = value
        return name, address, image, version, config, autostart

    def get_service_config(self, context, name, address, image, version, config, autostart):

        try:
            image_object = self.client.images.get(f'{image!s}:{version!s}')
        except docker_errors.ImageNotFound:
            message = f'Image {image!s}:{version!s} could not be found'
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        # check image labels
        if 'ams.services.agent' not in image_object.labels:
            message = f'Image {image!s}:{version!s} is missing the ams.service.agent label.'
            context.abort(grpc.StatusCode.NOT_FOUND, message)

        scale = int(autostart)
        labels = {}
        env = {}
        networks = set(['cloud_etcd'])  # TODO remove this and add a etcd network if required

        for label, cfg in image_object.labels.items():
            logger.debug("apply label %s with config %s", label, cfg)
            try:
                plugin = self.parent.services[label]
            except KeyError:
                continue

            # updating networks and environment
            n, e = plugin(cfg, **config)
            networks.update(n)
            env.update(e)

        if address:
            env.update({
                'AMS_ADDRESS': address,
            })

        # TODO
        #  curl -d '{"request": {"hosts": [""], "CN": "agent_name:image:version", "key": {"algo": "rsa", "size": 2096}}, "profile": "peer" }' 127.0.0.1:8888/api/v1/cfssl/newcert  # noqa

        env.update({
            'AMS_CORE': 'tasks.%s' % os.environ.get('SERVICE_NAME'),
            'AMS_AGENT': name,

            # TODO remove them
            'AMS_IMAGE': image,
            'AMS_VERSION': version,
            'AMS_ETCD_SERVER': "tasks.etcd",
            'AMS_PREFIX': self.prefix[0] + '_',
            'AMS_TYPE': self.prefix,
        })
        labels.update({
            'ams.autostart': '%s' % autostart,
            'ams.type': self.prefix,
        })
        networks = list(networks)

        return {
            "image": f'{image!s}:{version!s}',
            "name": name,
            "labels": labels,
            "env": env,
            "networks": networks,
            "log_driver": "json-file",
            "log_driver_options": {
                "max-file": "10",
                "max-size": "1m",
            },
            "mode": ServiceMode("replicated", scale),
            # "preferences": Placement(preferences=[("spread", "node.labels.worker")]),
        }

    # RPCs

    # === TODO

    def images(self, request, context):
        """
        """
        for image in self.client.images.list(filters={'label': ["ams.services.agent=true"]}):
            for tag in image.tags:
                pass
            # TODO yield data

    @agent_required
    def booted(self, request, context):
        logger.debug('booted called from %s', context._agent)
        try:
            self.parent.agent_booted(context._agent)
        except docker_errors.NotFound:
            message = 'Could not find %s' % context._agent
            context.abort(grpc.StatusCode.NOT_FOUND, message)
        return Empty()

    # === END TODO

    def agents(self, request, context):
        """
        """
        for service in self.client.services.list(filters={'label': ["ams.type=%s" % self.prefix]}):
            name, address, image, version, config, autostart = self.get_service_data(service)
            yield framework_pb2.AgentData(
                name=service.name,
                image=image,
                version=version,
                address=address,
                config=config,
                autostart=autostart,
            )

    def update(self, request, context):
        service = self.get_service(context, request.name)
        name, address, image, version, config, autostart = self.get_service_data(service)

        update = False

        if request.address and request.address != address:
            address = request.address
            update = True

        if request.image and request.image != image:
            image = request.image
            update = True

        if request.version and request.version != version:
            version = request.version
            update = True

        if request.config != config:
            config = request.config
            update = True

        if request.autostart != autostart:
            autostart = request.autostart
            update = True

        if update:
            service.update(**self.get_service_config(
                context,
                name,
                address,
                image,
                version,
                config,
                autostart,
            ))
        return framework_pb2.AgentData(name=name)

    @agent_required
    def create(self, request, context):
        logger.debug('create called from %s', context._agent)

        if self.RE_NAME.match(request.name):
            name = self.prefix[0] + '_' + request.name
        else:
            message = 'A name containing no special chars is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.image:
            message = 'An image is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if not request.version:
            message = 'A version is required to define agents'
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

        if request.config:
            try:
                config = json.loads(request.config)
            except json.JSONDecodeError:
                message = 'Config is not JSON parsable'
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)

            if config is None:
                config = {}
            elif not isinstance(config, dict):
                message = 'Config needs to be a json-dictionary %s' % request.config
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, message)
        else:
            config = {}

        services = self.client.services.list(filters={'label': ["ams.type=%s" % self.prefix], 'name': name})
        if services:
            message = 'Service with %s name already found' % name
            context.abort(grpc.StatusCode.ALREADY_EXISTS, message)

        self.client.services.create(**self.get_service_config(
            context,
            name,
            request.address,
            request.image,
            request.version,
            config,
            request.autostart,
        ))
        return framework_pb2.AgentData(name=name)

    @agent_required
    def destroy(self, request, context):
        logger.debug('destroy called from %s', context._agent)
        service = self.get_service(context, context._agent)
        service.remove()

        # TODO add destroy callbacks for plugins!
        # # cleanup database
        # for path in [
        #     f'agents/{context._agent!s}',
        # ]:
        #     self.etcd_client.delete_prefix(path.encode('utf-8'))
        return Empty()

    @agent_required
    def sleep(self, request, context):
        logger.debug('sleep called from %s', context._agent)
        service = self.get_service(context, context._agent)
        if service.attrs['Spec']['Mode']['Replicated']['Replicas'] > 0:
            logger.debug('scale service %s to 0', context._agent)
            service.scale(0)
        return Empty()

    @agent_required
    def upgrade(self, request, context):
        logger.debug('upgrade called from %s', context._agent)
        service = self.get_service(context, context._agent)
        service.force_update()
        return Empty()

    @agent_required
    def wake(self, request, context):
        logger.debug('wake called from %s', context._agent)
        service = self.get_service(context, context._agent)
        if service.attrs['Spec']['Mode']['Replicated']['Replicas'] > 0:
            logger.debug('scale service %s to 1', context._agent)
            service.scale(1)
        return Empty()

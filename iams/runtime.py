#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import base64
import hashlib
import logging
import os
import re

from socket import gethostname

from iams.exceptions import InvalidAgentName
from iams.interfaces.runtime import RuntimeInterface

import docker


logger = logging.getLogger(__name__)


class DockerSwarmRuntime(RuntimeInterface):

    RE_ENV = re.compile(r'^IAMS_(ADDRESS|PORT)=(.*)$')

    def __init__(self, ca, cfssl) -> None:
        super().__init__()
        self.ca = ca
        self.client = docker.DockerClient()

        self.cfssl = cfssl

        self.container = self.client.containers.get(gethostname())
        service = self.container.attrs["Config"]["Labels"]["com.docker.swarm.service.name"]

        self.label = "com.docker.stack.namespace"
        self.namespace = self.container.attrs["Config"]["Labels"][self.label]
        self.servername = "tasks." + service[len(self.namespace) + 1:]
        self.iams_namespace = "prod"

        self.regex = re.compile(r'^(%s_)?([a-zA-Z][a-zA-Z0-9-]+[a-zA-Z0-9])$' % self.iams_namespace[0:4])

    def get_valid_agent_name(self, name):
        regex = self.regex.match(name)
        if regex:
            return self.iams_namespace[0:4] + '_' + regex.group(2)
        else:
            raise InvalidAgentName("%s is not a valid agent-name" % name)

    def get_service_and_name(self, name):
        if isinstance(name, docker.models.services.Service):
            service = name
            name = service.name
        else:
            service = self.get_service(name)
        return service, name

    def get_agent_plugins(self, name):
        service, name = self.get_service_and_name(name)

        image, version = self.get_image_version(service)
        image_object = self.client.images.get(f'{image!s}:{version!s}')
        for plugin in self.plugins:
            label = plugin.label()
            if label is None:
                yield plugin, None
            elif label in image_object.labels:
                yield plugin, image_object.labels[label]

    def get_agent_config(self, name):
        service, name = self.get_service_and_name(name)

        configs = self.client.configs.list(filters={
            'name': name,
            "label": [
                f"{self.label}={self.namespace}",
                f"iams.namespace={self.iams_namespace}",
                f"iams.agent={name}",
            ],
        })
        if len(configs) == 1:
            return base64.decodebytes(configs[0].attrs["Spec"]["Data"].encode())
        else:
            return None

    def wake_agent(self, name):
        service, name = self.get_service(name)
        if service.attrs['Spec']['Mode']['Replicated']['Replicas'] != 1:
            logger.debug('scale service %s to 1', name)
            service.scale(1)

    def sleep_agent(self, name):
        service, name = self.get_service(name)
        if service.attrs['Spec']['Mode']['Replicated']['Replicas'] != 0:
            logger.debug('scale service %s to 0', name)
            service.scale(0)

    def delete_agent(self, name):
        service, name = self.get_service_and_name(name)
        logger.info("Delete agent: %s", name)
        service.remove()
        self.delete_agent_plugins(service)
        self.delete_agent_secrets(name)
        self.delete_agent_configs(name)
        return True

    def delete_agent_secrets(self, name):
        for secret in self.client.secrets.list(filters={"label": [
            f"{self.label}={self.namespace}",
            f"iams.namespace={self.iams_namespace}",
            f"iams.agent={name}",
        ]}):
            secret.remove()

    def delete_agent_configs(self, name):
        for config in self.client.configs.list(filters={"label": [
            f"{self.label}={self.namespace}",
            f"iams.namespace={self.iams_namespace}",
            f"iams.agent={name}",
        ]}):
            config.remove()

    def get_service(self, name):
        services = self.client.services.list(filters={
            'name': str(name),
            'label': [
                f"{self.label}={self.namespace}",
                f"iams.namespace={self.iams_namespace}",
            ],
        })

        if len(services) == 1:
            return services[0]
        else:
            raise docker.errors.NotFound('Could not find service %s' % name)

    def get_image_version(self, service):
        return service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)

    def update_agent(self, request, create=False, update=False, seed=None):
        try:
            service = self.get_service(request.name)
            scale = service.attrs['Spec']['Mode']['Replicated']['Replicas'] or int(request.autostart)

            image, version = self.get_image_version(service)
            address = None
            port = None
            for env in filter(self.RE_ENV.match, service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Env']):
                env_name, value = self.RE_ENV.match(env).groups()
                if env_name == "ADDRESS":
                    address = value
                if env_name == "PORT":
                    port = value
            config = self.get_agent_config(service)

            if request.image is None:
                request.image = image
            elif request.image != image:
                update = True

            if request.version is None:
                request.version = version
            elif request.version != version:
                update = True

            if request.address is None:
                request.address = address
            elif request.address != address:
                update = True

            if request.port is None:
                request.port = port
            elif request.port != port:
                update = True

            if request.config is None:
                request.config = config
            elif request.config != config:
                if request.config == '-':
                    request.config = None
                update = True

        except docker.errors.NotFound:
            create = True
            scale = int(request.autostart)

        if create and update:
            raise ValueError("service already exists")

        if request.image is None or request.version is None:
            raise ValueError("image and version must be set")

        # no changes occur
        if not update and not create:
            logger.debug("no changes occured - skip updating agent: %s", request.name)
            return None

        if create:
            logger.info("Create agent: %s", request.name)
        else:
            logger.info("Update agent: %s", request.name)

        # check image labels
        image_object = self.client.images.get(f'{request.image!s}:{request.version!s}')
        if 'iams.services.agent' not in image_object.labels:
            raise docker.errors.ImageNotFound(
                f'Image {request.image!s}:{request.version!s} is missing the iams.service.agent label.',
            )

        labels = {}
        env = {}
        networks = set()
        secrets = {}  # preconfigured secrets
        generated = []  # autogenerated secrets

        # plugin system
        for plugin in self.plugins:
            label = plugin.label()
            if label in image_object.labels:
                # apply plugin
                arg = image_object.labels[label]
                logger.debug("Apply plugin %s with %s", label, arg)
                e, l, n, s, g = plugin(request.name, request.image, request.version, arg)
                labels.update(l)
                env.update(e)
                networks.update(n)
                secrets.update(s)
                generated += g

        # set default values
        if request.address:
            env.update({
                'IAMS_ADDRESS': request.address,
            })
        if request.port:
            env.update({
                'IAMS_PORT': request.port,
            })

        if seed:
            env.update({
                'IAMS_SEED': seed,
            })

        env.update({
            'IAMS_AGENT': request.name,
            'IAMS_SERVICE': self.servername,
            # 'IAMS_SIMULATION': str(self.simulation).lower(),
        })

        # TODO check if needed
        if "IAMS_RUNTESTS" in os.environ:
            env.update({
                'IAMS_RUNTESTS': os.environ["IAMS_RUNTESTS"],
            })

        # for label in image_object.labels:
        #     if self.RE_ABILITY.match(label):
        #         labels.update({
        #             label: image_object.labels[label],
        #         })

        labels.update({
            self.label: self.namespace,
            'iams.namespace': self.iams_namespace,
            'iams.agent': request.name,
            'iams.image': request.image,
        })
        if "IAMS_NETWORK" in os.environ:
            networks.add(os.environ.get("IAMS_NETWORK"))
        networks = list(networks)

        # TODO this works but is ugly and hardcoded
        # get private_key and certificate
        secrets["%s_ca.crt" % self.namespace] = "ca.crt"
        response = self.cfssl.get_certificate(request.name, image=request.image, version=request.version)
        certificate = response["result"]["certificate"]
        private_key = response["result"]["private_key"]
        generated.append(("peer.crt", "peer.crt", certificate.encode()))
        generated.append(("peer.key", "peer.key", private_key.encode()))
        # TODO end

        # update all secrets from agent
        old_secrets = []
        new_secrets = []
        for secret_name, filename, data in generated:
            secret, old = self.set_secret(request.name, secret_name, data)
            new_secrets.append(docker.types.SecretReference(secret.id, secret.name, filename=filename))
            old_secrets += old

        # update all secrets from agent
        for key, filename in secrets.items():
            secret = self.client.secrets.get(key)
            new_secrets.append(docker.types.SecretReference(secret.id, secret.name, filename=filename))

        # update config
        logger.debug("using config %s", request.config)
        if request.config:
            config, old_configs = self.set_config(request.name, request.config)
            new_configs = [docker.types.ConfigReference(config.id, config.name, filename="/config")]
        else:
            new_configs = []
            old_configs = []

        if not request.preferences:
            # if self.simulation:
            #     request.preferences = ["node.labels.simulation"]
            # else:
            request.preferences.append("node.labels.worker")

        task_template = docker.types.TaskTemplate(
            container_spec=docker.types.ContainerSpec(
                f'{request.image!s}:{request.version!s}',
                env=env,
                configs=new_configs,
                secrets=new_secrets,
            ),
            log_driver=docker.types.DriverConfig("json-file", {"max-file": "10", "max-size": "1m"}),
            networks=networks,
            placement=docker.types.Placement(
                constraints=list(request.constraints),
                preferences=list([
                    docker.types.PlacementPreference('spread', pref) for pref in request.preferences
                ]),
            ),
        )

        if create:
            logger.debug("create task %s", task_template)
            self.client.api.create_service(
                task_template=task_template,
                name=request.name,
                labels=labels,
                mode=docker.types.ServiceMode("replicated", scale),
                networks=networks,
            )
            return True

        elif update:
            logger.debug("update task %s", task_template)
            self.client.api.update_service(
                service.id,
                service.version,
                task_template=task_template,
                name=request.name,
                labels=labels,
                mode=docker.types.ServiceMode("replicated", scale),
                networks=networks,
            )

        # delete old screts
        for secret in old_secrets:
            secret.remove()

        # delete old configs
        for config in old_configs:
            config.remove()

        return False

    def set_secret(self, service, name, data):
        md5 = hashlib.md5(service.encode())
        md5.update(data)
        md5 = md5.hexdigest()[0:8]
        secret_name = f"{service}_{name}_{md5}"

        # select
        secret = None
        old_secrets = []
        for s in self.client.secrets.list(filters={"label": [
            f"{self.label}={self.namespace}",
            f"iams.namespace={self.iams_namespace}",
            f"iams.agent={service}",
            f"iams.secret={name}",
        ]}):
            if s.name == secret_name:
                secret = s
            else:
                old_secrets.append(s)

        if secret is None:
            logger.debug('creating secret %s for %s', name, service)
            secret = self.client.secrets.create(
                name=secret_name,
                data=data,
                labels={
                    self.label: self.namespace,
                    'iams.namespace': self.iams_namespace,
                    'iams.agent': service,
                    'iams.secret': name,
                },
            )
            secret.reload()  # workarround for https://github.com/docker/docker-py/issues/2025
        return secret, old_secrets

    def set_config(self, service, data):
        if data:
            md5 = hashlib.md5(data)
            md5 = md5.hexdigest()[0:8]
            config_name = f"{service}_{md5}"
        else:
            config_name = None

        # select
        config = None
        old_configs = []
        for c in self.client.configs.list(filters={"label": [
            f"{self.label}={self.namespace}",
            f"iams.namespace={self.iams_namespace}",
            f"iams.agent={service}",
        ]}):
            if c.name == config_name:
                config = c
            else:
                old_configs.append(c)

        if config_name is not None and config is None:
            logger.debug('creating config for %s', service)
            config = self.client.configs.create(
                name=config_name,
                data=data,
                labels={
                    self.label: self.namespace,
                    'iams.namespace': self.iams_namespace,
                    'iams.agent': service,
                },
            )
            config.reload()  # workarround for https://github.com/docker/docker-py/issues/2025
        return config, old_configs


'''
class SimulationRuntime(RuntimeInterface):
    pass
'''

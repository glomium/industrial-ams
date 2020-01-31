#!/usr/bin/python
# ex:set fileencoding=utf-8:

import hashlib
import logging
import os
import re

import docker

from .cfssl import get_certificate


logger = logging.getLogger(__name__)


class Docker(object):

    RE_ENV = re.compile(r'^IAMS_(ADDRESS|PORT|CONFIG)=(.*)$')

    def __init__(self, namespace_docker, namespace_iams):
        self.client = docker.DockerClient()
        self.namespace = {
            "docker": namespace_docker,
            "iams": namespace_iams,
        }

    def del_service(self, name):
        service = self.get_service(name)
        service.remove()

        for secret in self.client.secrets.list(filters={"label": [
            f"com.docker.stack.namespace={self.namespace['docker']}",
            f"iams.namespace={self.namespace['iams']}",
            f"iams.agent={name}",
        ]}):
            secret.remove()

    def get_service(self, name):
        services = self.client.services.list(filters={
            'name': name,
            'label': [
                f"com.docker.stack.namespace={self.namespace['docker']}",
                f"iams.namespace={self.namespace['iams']}",
            ],
        })
        if len(services) == 1:
            return services[0]
        else:
            raise docker.errors.NotFound('Could not find service %s' % name)

    def set_secret(self, service, name, data):
        md5 = hashlib.md5(service.encode())
        md5.update(data)
        md5 = md5.hexdigest()[0:8]
        secret_name = f"{service}_{name}_{md5}"

        # select
        secret = None
        old_secrets = []
        for s in self.client.secrets.list(filters={"label": [
            f"com.docker.stack.namespace={self.namespace['docker']}",
            f"iams.namespace={self.namespace['iams']}",
            f"iams.agent={service}",
            f"iams.secret={name}",
        ]}):
            if s.name == secret_name:
                secret = s
            else:
                old_secrets.append(s)

        if secret is None:
            secret = self.client.secrets.create(
                name=secret_name,
                data=data,
                labels={
                    'com.docker.stack.namespace': self.namespace['docker'],
                    'iams.namespace': self.namespace['iams'],
                    'iams.agent': service,
                    'iams.secret': name,
                },
            )
            secret.reload()  # workarround for https://github.com/docker/docker-py/issues/2025
        return secret, old_secrets

    def set_service(
        self, name, image, version, address, port, config,
        plugins={}, autostart=True, update=False,
    ):

        try:
            service = self.get_service(name)
            create = False
            scale = service.attrs['Spec']['Mode']['Replicated']['Replicas'] or int(autostart)

            service_image, service_version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)  # noqa
            service_address = None
            service_config = None
            service_port = None
            for env in filter(self.RE_ENV.match, service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Env']):
                name, value = self.RE_ENV.match(env).groups()
                if name == "ADDRESS":
                    service_address = value
                if name == "PORT":
                    service_port = value
                if name == "CONFIG":
                    service_config = value

            # update if image changed
            if image is None or image == service_image:
                image = service_image
            else:
                update = True

            # update if version changed
            if version is None or version == service_version:
                version = service_version
            else:
                update = True

            # update if address changed
            if address is None or address == service_address:
                address = service_address
            else:
                if address == '-':
                    address = None
                update = True

            # update if port changed
            if port is None or port == service_port:
                port = service_port
            else:
                if port == -1:
                    port = None
                update = True

            # update if config changed
            if config is None or config == service_config:
                config = service_config
            else:
                if not config == '-':
                    config = None
                update = True

        except docker.errors.NotFound:
            create = True
            scale = int(autostart)

        # error if there is not image or version set
        if image is None or version is None:
            raise ValueError("image and version must be set")

        # no changes occur
        if not update and not create:
            return None

        # check image labels
        image_object = self.client.images.get(f'{image!s}:{version!s}')
        if 'iams.services.agent' not in image_object.labels:
            raise docker.errors.ImageNotFound(f'Image {image!s}:{version!s} is missing the iams.service.agent label.')

        labels = {}
        env = {}
        networks = set()
        secrets = {}  # preconfigured secrets
        generated = []  # autogenerated secrets

        # plugin system
        for label, cfg in image_object.labels.items():
            logger.debug("apply label %s with config %s", label, cfg)
            try:
                plugin = plugins[label]
            except KeyError:
                continue

            # updating networks and environment
            e, l, n, s, g = plugin(cfg, **config)
            networks.update(n)
            env.update(e)
            secrets.update(s)
            generated.append(g)

        # set default values
        if address:
            env.update({
                'IAMS_ADDRESS': address,
            })
        if port:
            env.update({
                'IAMS_PORT': port,
            })
        if config:
            env.update({
                'IAMS_CONFIG': config,
            })

        env.update({
            'IAMS_SERVICE': 'tasks.%s' % os.environ.get('SERVICE_NAME'),
            'IAMS_AGENT': name,
        })
        labels.update({
            'com.docker.stack.namespace': self.namespace['docker'],
            'iams.namespace': self.namespace['iams'],
            'iams.agent': name,
        })
        networks = list(networks)

        # === START TODO ======================================================
        # this works but is ugly and hardcoded
        # get private_key and certificate
        secrets["cloud_ca.pem"] = "ca.pem"
        response = get_certificate(name, image=image, version=version)
        certificate = response["result"]["certificate"]
        private_key = response["result"]["private_key"]
        generated.append(("own.crt", "own.crt", certificate.encode()))
        generated.append(("own.key", "own.key", private_key.encode()))
        # === END TODO ========================================================

        # update all secrets from agent
        old_secrets = []
        new_secrets = []
        for secret_name, filename, data in generated:
            secret, old = self.set_secret(name, secret_name, data)
            new_secrets.append(docker.types.SecretReference(secret.id, secret.name, filename=filename))
            old_secrets += old

        # update all secrets from agent
        for key, filename in secrets.items():
            secret = self.client.secrets.get(key)
            new_secrets.append(docker.types.SecretReference(secret.id, secret.name, filename=filename))

        kwargs = {
            "image": f'{image!s}:{version!s}',
            "name": name,
            "labels": labels,
            "env": env,
            "networks": networks,
            "secrets": new_secrets,
            "log_driver": "json-file",
            "log_driver_options": {
                "max-file": "10",
                "max-size": "1m",
            },
            "mode": docker.types.ServiceMode("replicated", scale),
            # "preferences": Placement(preferences=[("spread", "node.labels.worker")]),
        }

        if create:
            self.client.services.create(**kwargs)
            return True
        elif update:
            service.update(**kwargs)

        # delete old screts
        for secret in old_secrets:
            secret.remove()

        return False

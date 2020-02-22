#!/usr/bin/python
# ex:set fileencoding=utf-8:

import base64
import hashlib
import logging
import re
import os

import docker


logger = logging.getLogger(__name__)


class Docker(object):

    RE_ENV = re.compile(r'^IAMS_(ADDRESS|PORT)=(.*)$')
    RE_ABILITY = re.compile(r'^iams\.ability\.([a-z][a-z0-9]+)$')

    def __init__(self, client, cfssl, servername, namespace_docker, namespace_iams, simulation, plugins):
        self.client = client
        self.cfssl = cfssl
        self.namespace = {
            "docker": namespace_docker,
            "iams": namespace_iams,
        }
        self.servername = servername
        self.simulation = simulation
        self.plugins = plugins

    def del_service(self, name):
        if isinstance(name, docker.models.services.Service):
            service = name
            name = service.name
        else:
            service = self.get_service(name)

        image, version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)  # noqa
        service.remove()

        for secret in self.client.secrets.list(filters={"label": [
            f"com.docker.stack.namespace={self.namespace['docker']}",
            f"iams.namespace={self.namespace['iams']}",
            f"iams.agent={name}",
        ]}):
            secret.remove()

        for config in self.client.configs.list(filters={"label": [
            f"com.docker.stack.namespace={self.namespace['docker']}",
            f"iams.namespace={self.namespace['iams']}",
            f"iams.agent={name}",
        ]}):
            config.remove()

        # plugin system
        image_object = self.client.images.get(f'{image!s}:{version!s}')
        for plugin in self.plugins:
            if plugin.label in image_object.labels:
                # apply plugin
                plugin.remove(name, image_object.labels[plugin.label])

    def get_config(self, service):
        configs = self.client.configs.list(filters={
            'name': service,
            'label': [
                f"com.docker.stack.namespace={self.namespace['docker']}",
                f"iams.namespace={self.namespace['iams']}",
                f"iams.agent={service}",
            ],
        })
        if len(configs) == 1:
            return base64.decodebytes(configs[0].attrs["Spec"]["Data"].encode())
        else:
            return None

    def get_service(self, name=None):
        if name:
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
        else:
            return self.client.services.list(filters={
                'label': [
                    f"com.docker.stack.namespace={self.namespace['docker']}",
                    f"iams.namespace={self.namespace['iams']}",
                ],
            })

    def set_scale(self, name, scale):
        service = self.get_service(name)
        if service.attrs['Spec']['Mode']['Replicated']['Replicas'] != scale:
            logger.debug('scale service %s to %s', name, scale)
            service.scale(scale)

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
            f"com.docker.stack.namespace={self.namespace['docker']}",
            f"iams.namespace={self.namespace['iams']}",
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
                    'com.docker.stack.namespace': self.namespace['docker'],
                    'iams.namespace': self.namespace['iams'],
                    'iams.agent': service,
                },
            )
            config.reload()  # workarround for https://github.com/docker/docker-py/issues/2025
        return config, old_configs

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
            logger.debug('creating secret %s for %s', name, service)
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

    def update_secret(self, name, data):

        secret = self.client.secrets.get(name)
        try:
            secret.remove()
            self.client.secrets.create(
                name=name,
                data=data,
                labels=secret.attrs["Spec"].get("Labels", {}),
            )

        # There is no public api which selects the services related to an agent
        # This hack tries to remove the secret to obtain a list of connected services
        except docker.errors.APIError as e:
            names = e.explanation.rsplit(':', 1)[1].strip().split(', ')

            services = {}
            # remove secrets from service
            for s in names:
                service = self.client.services.get(s)
                secrets = []
                for obj in service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Secrets"]:
                    if obj["SecretName"] == name:
                        services[name] = obj
                    else:
                        secrets.append(obj)

                service.update(secrets=secrets)

            # remove secret
            secret.reload()
            secret.remove()

            # create new secret
            new_secret = self.client.secrets.create(
                name=name,
                data=data,
                labels=secret.attrs["Spec"].get("Labels", {}),
            )

            for s in names:
                service = self.client.services.get(s)
                add = services[name]
                add["SecretID"] = new_secret.id

                secrets = service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"].get("Secrets", {})
                secrets.append(add)
                service.update(secrets=secrets)

    def set_service(
        self, name, image=None, version=None, address=None, port=None, config=None,
        autostart=True, create=False, update=False, seed=None,
    ):

        try:
            service = self.get_service(name)
            scale = service.attrs['Spec']['Mode']['Replicated']['Replicas'] or int(autostart)

            service_image, service_version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].rsplit(':', 1)  # noqa
            service_address = None
            service_port = None
            for env in filter(self.RE_ENV.match, service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Env']):
                env_name, value = self.RE_ENV.match(env).groups()
                if env_name == "ADDRESS":
                    service_address = value
                if env_name == "PORT":
                    service_port = value

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
            service_config = self.get_config(name)
            if config is None or config == service_config:
                config = service_config
            else:
                if config == '-':
                    config = None
                update = True

        except docker.errors.NotFound:
            create = True
            scale = int(autostart)

        if create and update:
            raise ValueError("service already exists")

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
        for plugin in self.plugins:
            if plugin.label in image_object.labels:
                # apply plugin
                e, l, n, s, g = plugin(
                    self.namespace["docker"], name, image, version,
                    image_object.labels[plugin.label],
                )
                labels.update(l)
                env.update(e)
                networks.update(n)
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
        if seed:
            env.update({
                'IAMS_SEED': seed,
            })

        env.update({
            'IAMS_AGENT': name,
            'IAMS_SERVICE': self.servername,
            'IAMS_SIMULATION': str(self.simulation).lower(),
        })
        for label in image_object.labels:
            if self.RE_ABILITY.match(label):
                labels.update({
                    label: image_object.labels[label],
                })

        labels.update({
            'com.docker.stack.namespace': self.namespace['docker'],
            'iams.namespace': self.namespace['iams'],
            'iams.agent': name,
            'iams.image': image,
        })
        if "IAMS_NETWORK" in os.environ:
            networks.add(os.environ.get("IAMS_NETWORK"))

        networks = list(networks)

        # TODO this works but is ugly and hardcoded
        # get private_key and certificate
        secrets["%s_ca.crt" % self.namespace["docker"]] = "ca.crt"
        response = self.cfssl.get_certificate(name, image=image, version=version)
        certificate = response["result"]["certificate"]
        private_key = response["result"]["private_key"]
        generated.append(("peer.crt", "peer.crt", certificate.encode()))
        generated.append(("peer.key", "peer.key", private_key.encode()))

        # update all secrets from agent
        old_secrets = []
        new_secrets = []
        for secret_name, filename, data in generated:
            secret, old = self.set_secret(name, secret_name, data)
            new_secrets.append(docker.types.SecretReference(secret.id, secret.name, filename=filename))
            old_secrets += old

        # update config
        logger.debug("using config %s", config)
        if config:
            config, old_configs = self.set_config(name, config)
            configs = [docker.types.ConfigReference(config.id, config.name, filename="/config")]
        else:
            configs = []
            old_configs = []

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
            "configs": configs,
            "secrets": new_secrets,
            "log_driver": "json-file",
            "log_driver_options": {
                "max-file": "10",
                "max-size": "1m",
            },
            "mode": docker.types.ServiceMode("replicated", scale),
            "preferences": [docker.types.Placement(preferences=[("spread", "node.labels.worker")])],
        }

        if create:
            self.client.services.create(**kwargs)
            return True
        elif update:
            service.update(**kwargs)

        # delete old screts
        for secret in old_secrets:
            secret.remove()

        # delete old configs
        for config in old_configs:
            config.remove()

        return False

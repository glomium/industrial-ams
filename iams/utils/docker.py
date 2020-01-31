#!/usr/bin/python
# ex:set fileencoding=utf-8:

import hashlib
import re

import docker


RE_ENV = re.compile(r'^IAMS_(ADDRESS|KWARGS)=(.*)$')


def get_service(client, namespace, name):
    services = self.client.services.list(filters={
        'name': name,
        'label': [
            f"com.docker.stack.namespace={namespace['docker']}",
            f"iams.namespace={namespace['iams']}",
        ],
    })
    if len(services) == 1:
        return services[0]
    else:
        raise docker.errors.NotFound('Could not find service %s' % name)


def create_or_update_secret(client, namespace, service_name, name, data):

    created = False
    md5 = hashlib.md5(service_name.encode())
    md5.update(data)
    secret_name = f"{service_name}_{name}_{md5}"

    # select 
    secret = None
    old_secrets = []
    for s in client.secrets.list(filters={"label": [
            f"com.docker.stack.namespace={namespace['docker']}",
            f"iams.namespace={namespace['iams']}",
            f"iams.agent={service_name}",
            f"iams.secret={name}",
        ]}):
        if s.name == secret_name:
            secret = s
        else:
            old_secrets.append(s)

    if secret is None:
        created = True
        secret = client.secrets.create(
            secret_name,
            data=data,
            labels={
                'com.docker.stack.namespace': namespace['docker'],
                'iams.namespace': namespace['iams'],
                'iams.agent': agent,
                'iams.secret': name,
            },
        )
        # secret.reload()  # workarround for https://github.com/docker/docker-py/issues/2025
    return created, secret.id, old_secrets


def create_or_update_service(client, namespace, name, address, image, version, config, plugins=[], autostart=True, force=False):
    try:
        service = get_service(client, namespace, name)
        create = False
        scale = service.attrs['Spec']['Mode']['Replicated']['Replicas'] or int(autostart)
    except docker.errors.NotFound:
        create = True
        scale = int(autostart)

    image_object = self.client.images.get(f'{image!s}:{version!s}')
    # check image labels
    if 'iams.services.agent' not in image_object.labels:
        raise docker_errors.ImageNotFound(f'Image {image!s}:{version!s} is missing the ams.service.agent label.')

    labels = {}
    env = {}
    networks = set()
    secrets = []
    update = False

    # plugin system
    for label, cfg in image_object.labels.items():
        logger.debug("apply label %s with config %s", label, cfg)
        try:
            plugin = self.plugins[label]
        except KeyError:
            continue
    
        # updating networks and environment
        e, l, n, s = plugin(cfg, **config)
        networks.update(n)
        env.update(e)
        secrets += s

    if address:
        env.update({
            'IAMS_ADDRESS': address,
        })
    env.update({
        'IAMS_SERVICE': 'tasks.%s' % os.environ.get('SERVICE_NAME'),
        'IAMS_AGENT': name,
    })
    labels.update({
        'com.docker.stack.namespace': namespace['docker'],
        'iams.namespace': namespace['iams'],
    })
    networks = list(networks)

    # update all secrets from agent
    old_secrets = []
    new_secrets = []
    for secret_name, filename, data in secrets:
        created, secret_id, old = create_or_update_secret(client, namespace, name, secret_name, data)
        new_secrets.append(docker.types.SecretReference(secret_id, filename))
        old_secrets.append(old)
        if created:
            update = True

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
        "mode": ServiceMode("replicated", scale),
        # "preferences": Placement(preferences=[("spread", "node.labels.worker")]),
    }

    if create:
        self.client.services.create(**kwargs)
    elif update:
        self.client.services.update(**kwargs)


def get_service_config(self, service):
    image, version = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'].rsplit('@')[0].image.rsplit(':', 1)  # noqa
    autostart = service.attrs['Spec']['Labels'].get('ams.autostart', None) == 'True'
    address = None
    config = None
    for env in filter(RE_ENV.match, service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Env']):
        name, value = RE_ENV.match(env).groups()
        if name == "ADDRESS":
            address = value
        if name == "KWARGS":
            config = value
    return name, address, image, version, config, autostart


#   def get_service_config(self, context, name, address, image, version, config, autostart):

#       try:
#           image_object = self.client.images.get(f'{image!s}:{version!s}')
#       except docker_errors.ImageNotFound:
#           message = f'Image {image!s}:{version!s} could not be found'
#           context.abort(grpc.StatusCode.NOT_FOUND, message)

#       # check image labels
#       if 'ams.services.agent' not in image_object.labels:
#           message = f'Image {image!s}:{version!s} is missing the ams.service.agent label.'
#           context.abort(grpc.StatusCode.NOT_FOUND, message)

#       scale = int(autostart)
#       labels = {}
#       env = {}
#       networks = set()
#       secrets = {}

#       # plugin system
#       for label, cfg in image_object.labels.items():
#           logger.debug("apply label %s with config %s", label, cfg)
#           try:
#               plugin = self.plugins[label]
#           except KeyError:
#               continue

#           # updating networks and environment
#           e, l, n, s = plugin(cfg, **config)
#           networks.update(n)
#           env.update(e)
#           secrets.update(s)

#       if address:
#           env.update({
#               'AMS_ADDRESS': address,
#           })

#       env.update({
#           'AMS_CORE': 'tasks.%s' % os.environ.get('SERVICE_NAME'),
#           'AMS_AGENT': name,
#       })
#       labels.update({
#           'ams.autostart': str(autostart).lower(),
#           'ams.type': self.prefix,
#       })
#       networks = list(networks)
#       secrets.update({
#           'client.key': b'123123',
#       })

#       # remove all secrets from agent
#       for secret in client.secrets.list(filters={"label": [f'iams.agent={name}']}):
#           secret.remove()
#       # create secrets
#       for filename, data in secrets:
#           try:
#               client.secrets.create(name=filename, data=data, labels={"iams.agent": name})
#           except KeyError:
#               # workarround for https://github.com/docker/docker-py/issues/2025
#               pass

#       return {
#           "image": f'{image!s}:{version!s}',
#           "name": name,
#           "labels": labels,
#           "env": env,
#           "networks": networks,
#           "secrets": client.secrets.list(filters={"label": [f'iams.agent={name}']}),
#           "log_driver": "json-file",
#           "log_driver_options": {
#               "max-file": "10",
#               "max-size": "1m",
#           },
#           "mode": ServiceMode("replicated", scale),
#           # "preferences": Placement(preferences=[("spread", "node.labels.worker")]),
#       }

#   def update(self, request, context):
#       service = self.get_service(context, request.name)
#       name, address, image, version, config, autostart = self.get_service_data(service)

#       update = False

#       if request.address and request.address != address:
#           address = request.address
#           update = True

#       if request.image and request.image != image:
#           image = request.image
#           update = True

#       if request.version and request.version != version:
#           version = request.version
#           update = True

#       if request.config != config:
#           config = request.config
#           update = True

#       if request.autostart != autostart:
#           autostart = request.autostart
#           update = True

#       if update:
#           service.update(**self.get_service_config(
#               context,
#               name,
#               address,
#               image,
#               version,
#               config,
#               autostart,
#           ))
#       return framework_pb2.AgentData(name=name)

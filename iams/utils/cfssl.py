#!/usr/bin/python
# ex:set fileencoding=utf-8:

import logging
import os

import requests

from .auth import set_credentials


logger = logging.getLogger(__name__)


def get_ca_public_key():
    url = 'http://%s/api/v1/cfssl/info' % os.environ.get('IAMS_CFSSL')
    response = requests.post(url, json={}).json()

    if response["success"]:
        return response["result"]["certificate"].encode()
    return None


def get_certificate(name, hosts=None, image=None, version=None, algo="rsa", size=2096):

    if image is None and version is None:
        cn = set_credentials(None, None, None, [name])
        if hosts is None:
            profile = "client"
            hosts = [""]
        else:
            profile = "peer"
    else:
        cn = set_credentials(name, image, version, None)
        profile = "peer"
        hosts = ["127.0.0.1", "localhost", name]

    url = 'http://%s/api/v1/cfssl/newcert' % os.environ.get('IAMS_CFSSL')
    data = {
        "request": {
            "hosts": hosts,
            "CN": cn,
            "key": {
                "algo": algo,
                "size": size,
            },
            "profile": profile,
        },
    }
    logger.debug('request to %s: %s', url, data)
    response = requests.post(url, json=data).json()
    return response

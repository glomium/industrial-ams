#!/usr/bin/python
# ex:set fileencoding=utf-8:

import logging

import requests

from .auth import set_credentials


logger = logging.getLogger(__name__)


class CFSSL(object):

    def __init__(self, addr, size):
        self.addr = addr
        self.size = size
        url = f'http://{self.addr}/api/v1/cfssl/info'
        response = requests.post(url, json={}).json()
        self.ca = response["result"]["certificate"].encode()

    def get_certificate(self, name, hosts=None, image=None, version=None, groups=[], algo="rsa", size=None):
        if image is None and version is None:
            cn = set_credentials(None, None, None, name, groups)
            if hosts is None:
                profile = "client"
                hosts = [""]
            else:
                profile = "peer"
        else:
            cn = set_credentials(name, image, version, None, groups)
            profile = "peer"
            hosts = ["127.0.0.1", "localhost", name]

        hosts = [""]

        return self._get_certificate(cn, hosts, profile, algo, size)

    def _get_certificate(self, cn, hosts=[""], profile="peer", algo="rsa", size=None):
        url = f'http://{self.addr}/api/v1/cfssl/newcert'
        data = {
            "request": {
                "hosts": hosts,
                "CN": cn,
                "key": {
                    "algo": algo,
                    "size": size or self.size,
                },
                "profile": profile,
            },
        }
        logger.debug('request to %s: %s', url, data)
        response = requests.post(url, json=data).json()
        return response

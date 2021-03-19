#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import requests

from iams.interfaces.ca import CertificateAuthorityInterface


logger = logging.getLogger(__name__)


class CFSSL(CertificateAuthorityInterface):

    def __init__(self, service, hosts=[], rsa=2048):
        self.service = service
        self.rsa_size = rsa
        self.hosts = ["127.0.0.1", "localhost"] + hosts
        self.root_ca = None

    def __call__(self):
        response = requests.post(f'http://{self.service}/api/v1/cfssl/info', json={}).json()
        self.root_ca = response["result"]["certificate"].encode()

    def get_root_ca(self):
        return self.root_ca

    def set_credentials(self, agent=None, image=None, version=None, username=None, groups=[]):
        if agent is not None:
            return json.dumps([agent, image, version, groups])
        else:
            return json.dumps([username, groups])

    def get_certificate(self, name, hosts=None, image=None, version=None, groups=[], algo="rsa", size=None):
        if image is None and version is None:
            cn = self.set_credentials(None, None, None, name, groups)
            profile = "peer"
            hosts += self.hosts
        else:
            cn = self.set_credentials(name, image, version, None, groups)
            profile = "peer"
            hosts = [name] + self.hosts

        return self._get_certificate(cn, hosts, profile, algo, size)

    def _get_certificate(self, cn, hosts=[""], profile="peer", algo="rsa", size=None):
        url = f'http://{self.service}/api/v1/cfssl/newcert'
        data = {
            "request": {
                "hosts": hosts,
                "CN": cn,
                "key": {
                    "algo": algo,
                    "size": size or self.rsa_size,
                },
                "profile": profile,
            },
        }
        logger.debug('request to %s: %s', url, data)
        response = requests.post(url, json=data).json()
        return response

    def get_agent_certificate(self, name, image, version):
        response = self.get_certificate(name, image=image, version=version)
        certificate = response["result"]["certificate"].encode()
        private_key = response["result"]["private_key"].encode()
        return certificate, private_key

    def get_service_certificate(self, name, hosts):
        response = self.get_certificate(hosts[0], hosts=hosts, groups=[name])
        certificate = response["result"]["certificate"].encode()
        private_key = response["result"]["private_key"].encode()
        return certificate, private_key

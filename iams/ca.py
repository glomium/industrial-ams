#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

"""
Certificate authorities
"""

import logging
import requests

from iams.interfaces.ca import CertificateAuthorityInterface


logger = logging.getLogger(__name__)


class CFSSL(CertificateAuthorityInterface):
    """
    CFSSL as CA
    """

    def __init__(self, service_uri, hosts=None):
        self.service = service_uri
        self.hosts = ["127.0.0.1", "localhost"]
        if hosts:
            self.hosts += hosts
        self.root_ca = None
        logger.debug("CFSSL(%s, %s)", service_uri, self.hosts)

    def __call__(self):
        response = requests.post(f'http://{self.service}/api/v1/cfssl/info', json={}).json()
        self.root_ca = response["result"]["certificate"].encode()

    def get_ca_secret(self, data, namespace):
        data["%s_ca.crt" % namespace] = "ca.crt"
        return data

    def get_root_cert(self):
        """
        gets the root CA
        """
        return self.root_ca

    # pylint: disable=invalid-name
    def get_certificate(self, agent=None, cn=None, hosts=None):
        """
        get certificate from ca
        """
        if agent is None:
            if hosts is None:
                hosts = [""]
                profile = "client"
            elif hosts is True:
                hosts = self.hosts
                profile = "peer"
            else:
                hosts += self.hosts
                profile = "peer"
        else:
            cn = agent
            if hosts:
                hosts += self.hosts
            else:
                hosts = self.hosts
            profile = "peer"

        if cn and cn not in hosts:
            hosts = [cn] + hosts

        # return self._get_certificate(cn, hosts, profile, "rsa", 2048)
        return self._get_certificate(cn, hosts, profile, "ecdsa", 256)

    # pylint: disable=invalid-name,too-many-arguments
    def _get_certificate(self, cn, hosts, profile, algo, size):
        url = f'http://{self.service}/api/v1/cfssl/newcert'
        data = {
            "request": {
                "hosts": hosts or [""],
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

    # pylint: disable=
    def get_agent_certificate(self, name, hosts=None):
        response = self.get_certificate(agent=name, hosts=hosts)
        certificate = response["result"]["certificate"].encode()
        private_key = response["result"]["private_key"].encode()
        return certificate, private_key

    def get_service_certificate(self, name, hosts=None):
        response = self.get_certificate(cn=name, hosts=hosts)
        certificate = response["result"]["certificate"].encode()
        private_key = response["result"]["private_key"].encode()
        return certificate, private_key

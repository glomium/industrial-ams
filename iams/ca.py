#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from iams.interfaces.ca import CertificateAuthorityInterface
from iams.utils.cfssl import CFSSL as CFSSL_OLD


logger = logging.getLogger(__name__)


class CFSSL(CertificateAuthorityInterface):

    def __init__(self, service, hosts=[], rsa=2048):
        if hosts:
            hosts = ["127.0.0.1", "localhost"] + hosts
        else:
            hosts = ["127.0.0.1", "localhost"]
        self.cfssl = CFSSL_OLD(service, rsa, hosts)
        self.root = self.cfssl.ca

    def __call__(self):
        pass

    def get_agent_certificate(self, name, image, version):
        response = self.cfssl.get_certificate(name, image=image, version=version)
        certificate = response["result"]["certificate"].encode()
        private_key = response["result"]["private_key"].encode()
        return certificate, private_key

    def get_service_certificate(self, name, hosts):
        response = self.cfssl.get_certificate(hosts[0], hosts=hosts, groups=[name])
        certificate = response["result"]["certificate"].encode()
        private_key = response["result"]["private_key"].encode()
        return certificate, private_key

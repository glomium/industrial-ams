#!/usr/bin/python
# ex:set fileencoding=utf-8:

from iams.interfaces.ca import CertificateAuthorityInterface


class CA(CertificateAuthorityInterface):

    def __call__(self):
        pass

    def get_ca_secret(self, data, namespace):
        return data

    def get_agent_certificate(self, name, hosts=None):
        return b'None', b'None'

    def get_service_certificate(self, name, hosts=None):
        return b'None', b'None'

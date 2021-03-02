#!/usr/bin/python
# ex:set fileencoding=utf-8:

from iams.interfaces.ca import CertificateAuthorityInterface


class CA(CertificateAuthorityInterface):

    def __call__(self):
        pass

    def get_agent_certificate(self, name, image, version):
        return b'None', b'None'

    def get_service_certificate(self, name, hosts):
        return b'None', b'None'

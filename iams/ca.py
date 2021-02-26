#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging

from iams.interfaces.ca import CertificateAuthorityInterface


logger = logging.getLogger(__name__)


class CFSSL(CertificateAuthorityInterface):
    pass

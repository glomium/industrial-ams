#!/usr/bin/python
# ex:set fileencoding=utf-8:

import logging
import os
import socket
import ssl

from ..constants import AGENT_PORT


logger = logging.getLogger(__name__)


def validate_certificate(hostname=None, port=None):
    if hostname is None:
        hostname = os.environ.get('IAMS_SERVICE', None)
        if not hostname:
            return None
    if port is None:
        port = AGENT_PORT

    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        try:
            with context.wrap_socket(sock, server_hostname=hostname):
                return True
        except ssl.CertificateError:
            logger.debug("CertificateError, while connecting to %s", hostname)
            return False
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ssl
"""

import logging
import os
import socket
import ssl

from ..constants import AGENT_PORT


logger = logging.getLogger(__name__)


def validate_certificate(hostname=None, port=None):
    """
    validate certificate
    """
    if hostname is None:
        hostname = os.environ.get('IAMS_SERVICE', None)
        if not hostname:
            return None
    if port is None:
        port = AGENT_PORT

    logger.info("Connecting to %s:%s to validate ssl certificate", hostname, port)

    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        try:
            with context.wrap_socket(sock, server_hostname=hostname):
                return True
        except ssl.CertificateError:
            logger.debug("CertificateError, while connecting to %s", hostname)
            return False

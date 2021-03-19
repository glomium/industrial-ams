#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from iams.ca import CFSSL


cfssl = CFSSL("localhost:8888", rsa=2048)
try:
    cfssl()
except Exception as e:  # pragma: no cover
    SKIP = str(e)
else:
    SKIP = None


@unittest.skipIf(SKIP is not None, SKIP)
class CFSSLTests(unittest.TestCase):  # pragma: no cover
    def test_get_root_certificate(self):
        ca = cfssl.get_root_ca()
        self.assertEqual(ca[:27], b'-----BEGIN CERTIFICATE-----')

    def test_agent_certificate(self):
        crt, pk = cfssl.get_agent_certificate('agent_name', 'image', 'version')
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:31], b'-----BEGIN RSA PRIVATE KEY-----')

    def test_service_certificate(self):
        crt, pk = cfssl.get_service_certificate('service_name', hosts=['service_name'])
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:31], b'-----BEGIN RSA PRIVATE KEY-----')

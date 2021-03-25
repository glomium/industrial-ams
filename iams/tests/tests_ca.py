#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest

from iams.ca import CFSSL


cfssl = CFSSL("localhost:8888")
try:
    cfssl()
except Exception as e:  # pragma: no cover
    SKIP = str(e)
else:
    SKIP = None


@unittest.skipIf(SKIP is not None, SKIP)
class CFSSLTests(unittest.TestCase):  # pragma: no cover
    def test_init(self):
        CFSSL("localhost:8888", hosts=["*.domain"])

    def test_get_ca_secret(self):
        ca = cfssl.get_ca_secret({}, "test")
        self.assertEqual(ca, {'test_ca.crt': "ca.crt"})

    def test_get_root_certificate1(self):
        ca = cfssl.get_root_ca()
        self.assertEqual(ca[:27], b'-----BEGIN CERTIFICATE-----')

    def test_agent_certificate1(self):
        crt, pk = cfssl.get_agent_certificate('agent_name')
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:30], b'-----BEGIN EC PRIVATE KEY-----')

    def test_agent_certificate2(self):
        crt, pk = cfssl.get_agent_certificate('agent_name', hosts=["agent_name"])
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:30], b'-----BEGIN EC PRIVATE KEY-----')

    def test_service_certificate1(self):
        crt, pk = cfssl.get_service_certificate('service_name')
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:30], b'-----BEGIN EC PRIVATE KEY-----')

    def test_service_certificate2(self):
        crt, pk = cfssl.get_service_certificate('service_name', hosts=True)
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:30], b'-----BEGIN EC PRIVATE KEY-----')

    def test_service_certificate3(self):
        crt, pk = cfssl.get_service_certificate('service_name', hosts=["service_name"])
        self.assertEqual(crt[:27], b'-----BEGIN CERTIFICATE-----')
        self.assertEqual(pk[:30], b'-----BEGIN EC PRIVATE KEY-----')

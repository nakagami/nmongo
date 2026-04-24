#!/usr/bin/env python3
# coding:utf-8
###############################################################################
# MIT License
#
# Copyright (c) 2016, 2025 Hajime Nakagami
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
###############################################################################
# Test script for connecting nmongo to DocumentDB (https://github.com/documentdb/documentdb)
#
# Prerequisites:
#   docker run -dt -p 10260:10260 --name documentdb-container \
#     ghcr.io/documentdb/documentdb/documentdb-local:latest \
#     --username <YOUR_USERNAME> --password <YOUR_PASSWORD>
#
# Usage:
#   DOCUMENTDB_USER=<username> DOCUMENTDB_PASSWORD=<password> python test_documentdb.py
###############################################################################
import os
import unittest
from test_nmongo import TestBase


class TestDocumentDB(TestBase, unittest.TestCase):
    user = os.getenv('DOCUMENTDB_USER', 'testuser')
    password = os.getenv('DOCUMENTDB_PASSWORD', 'testpassword')
    host = os.getenv('DOCUMENTDB_HOST', 'localhost')
    port = int(os.getenv('DOCUMENTDB_PORT', '10260'))
    database = 'test_nmongo'
    use_ssl = True
    ssl_ca_certs = None  # TLS without certificate verification (tlsAllowInvalidCertificates=true)
    mechanism = 'SCRAM-SHA-256'

    def test_documentdb_index(self):
        self.db.pets.createIndex(
            {'name': 1, 'gender': -1},
            options={'name': 'name1'}
        )
        self.db.pets.createIndex(
            {'name': -1},
            options={'name': 'name2'}
        )

        indexes = self.db.pets.getIndexes()
        self.assertIn('name1', [idx['name'] for idx in indexes])
        self.db.pets.dropIndex('name1')
        self.assertFalse('name1' in [idx['name'] for idx in self.db.pets.getIndexes()])

        self.db.pets.dropIndexes()
        self.assertEqual(len(self.db.pets.getIndexes()), 1)

    def test_is_clapped(self):
        self.assertTrue(self.db.pets.stats()['ok'])
        self.skipTest('Capped collections not supported by DocumentDB')

    def test_servr_status(self):
        # serverStatus command is not supported by DocumentDB
        self.assertEqual(self.db.stats()['db'], self.database)

    @unittest.skip('mapReduce command not supported by DocumentDB')
    def test_map_reduce(self):
        self.assertTrue(
            self.db.pets.mapReduce(
                "function(){}",             # map
                "function(key, values){}",  # reduce
                {'out': {'inline': 1}}
            )['ok']
        )

    @unittest.skip('group command not supported by DocumentDB')
    def test_group(self):
        self.assertTrue(
            self.db.pets.group(
                {'name': 1, 'gender': 1},     # key
                "function (c, r) {}",       # reduce
                {},                         # initial
                cond={'gender': 'm'},
            )['ok']
        )


if __name__ == "__main__":
    unittest.main()

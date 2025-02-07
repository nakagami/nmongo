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
import os
import unittest
from test_nmongo import TestBase


class TestAzureCosmosDB(TestBase, unittest.TestCase):
    user = os.environ['COSMOSDB_USER']
    password = os.environ['COSMOSDB_PASSWORD']
    host = ".".join([user, "mongo.cosmos.azure.com"])
    database = 'test_nmongo'
    port = 10255
    use_ssl = True

    def test_azure(self):
        self.db.pets.createIndex(
            {'name': 1, 'gender': -1},
            options={'name': 'name1'}
        )
        self.db.pets.createIndex(
            {'name': -1},
            options={'name': 'name2'}
        )

        indexes = self.db.pets.getIndexes()
        self.assertEqual(3, len(indexes))
        self.db.pets.dropIndex('name1')  # drop name1
        self.assertEqual(len(self.db.pets.getIndexes()), 2)

        self.db.pets.dropIndexes()
        self.assertEqual(len(self.db.pets.getIndexes()), 1)


if __name__ == "__main__":
    unittest.main()

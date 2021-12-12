#!/usr/bin/env python3
# coding:utf-8
###############################################################################
# MIT License
#
# Copyright (c) 2016 Hajime Nakagami
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
import sys
import os
import unittest
import datetime
import nmongo
try:
    from decimal import Decimal
except ImportError:
    from nmongo import Decimal


class TestBase:
    # ssl_ca_certs = '/etc/ssl/mongodb-cert.crt'
    ssl_ca_certs = None
    user = None
    password = ''

    def assertEqualDict(self, d1, d2):
        self.assertEqual(set(d1.keys()), set(d2.keys()))
        for k, v in d1.items():
            self.assertEqual(d2.get(k), v)

    def setUp(self):
        self.db = nmongo.connect(
            self.host,
            self.database,
            port=self.port,
            user=self.user,
            password=self.password,
            use_ssl=self.use_ssl,
            ssl_ca_certs=self.ssl_ca_certs
        )
        self.db.pets.drop()
        self.mongo_version = [int(n) for n in self.db.version().split('.')][:2]

        self.data1 = {
            'name': 'Kitty',
            'gender': 'f',
            'age': 0,
            'species': 'cat',
        }
        if self.mongo_version > [3, 2]:
            self.data1['weight'] = Decimal("123.4")

        if sys.implementation.name != 'micropython':
            self.data1['birth'] = datetime.datetime(1974, 11, 1, 1, 1)
        self.data2 = {
            'name': 'Snoopy',
            'gender': 'm',
            'age': 0,
            'species': 'cat',
        }
        if self.mongo_version > [3, 2]:
            self.data2['weight'] = Decimal("1234.0")
        self.data3 = {
            'name': 'Kuri',
            'gender': 'm',
            'age': 0,
            'species': 'ferret',
        }
        if self.mongo_version > [3, 2]:
            self.data3['weight'] = Decimal("NaN")

        # Create
        self.db.pets.insert(self.data1)
        self.db.pets.insert([self.data2, self.data3])
        self.assertIn('pets', self.db.getCollectionNames())

    def tearDown(self):
        self.db.close()

    def test_base(self):

        # Read
        cur = self.db.pets.find(projection={'_id': 0})
        self.assertEqualDict(cur.fetchone(), self.data1)

        self.assertEqual(self.db.pets.count(), 3)

        self.assertEqual(set(self.db.pets.distinct('gender')), set(['m', 'f']))

        # findAndModify
        prev_data1 = self.db.pets.findAndModify(
            query={'name': 'Kitty'},
            update={'$inc': {'age': 1}},
        )
        next_data1 = self.db.pets.findOne({'name': 'Kitty'})
        self.assertEqual(prev_data1['age'] + 1, next_data1['age'])

        # Update
        r = self.db.pets.update(
            {'name': 'Snoopy'},
            {'name': 'Snoopy', 'gender': 'f', 'age': 10, 'species': 'wolf'}
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['nModified'], 1)
        self.assertEqualDict(
            self.db.pets.findOne({'name': 'Snoopy'}, projection={'_id': 0}),
            {'name': 'Snoopy', 'gender': 'f', 'age': 10, 'species': 'wolf'},
        )

        r = self.db.pets.updateOne(
            {'name': 'Snoopy'},          # query
            {'$set': {'gender': 'm'}, '$inc': {'age': 1}},  # update
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['nModified'], 1)
        self.assertEqual(
            self.db.pets.findOne({'name': 'Snoopy'}, projection={'_id': 0}),
            {'name': 'Snoopy', 'gender': 'm', 'age': 11, 'species': 'wolf'},
        )

        self.assertEqual(self.db.pets.count(), 3)
        r = self.db.pets.updateMany(
            {},                     # query
            {'$inc': {'age': 1}},   # update
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['n'], 3)
        self.assertEqual(r['nModified'], 3)
        r = self.db.pets.updateMany(
            {'name': {'$eq': 'Kitty'}},     # query
            {'$set': {'gender': 'f'}},      # update
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['n'], 1)
        self.assertEqual(r['nModified'], 0)

        # Delete
        self.assertEqual(self.db.pets.count(), 3)
        self.db.pets.insert(self.data1)
        self.assertEqual(self.db.pets.count(), 4)
        self.assertEqual(self.db.pets.remove({'name': 'Kitty', 'age': 0}), 1)
        self.assertEqual(self.db.pets.count(), 3)
        self.assertEqual(self.db.pets.findOneAndDelete({'name': 'Kitty'})['age'], 2)
        self.assertEqual(self.db.pets.count(), 2)

        # insertOne, insertMany
        self.db.pets.drop()
        oid = self.db.pets.insertOne(self.data1)
        self.assertEqual(
            self.db.pets.find({'_id': oid}).fetchone()['name'],
            self.data1['name']
        )
        oids = self.db.pets.insertMany([self.data2, self.data3])
        self.assertEqual(
            self.db.pets.find({'_id': oids[0]}).fetchone()['name'],
            self.data2['name']
        )

    def test_decimal(self):
        datum = [
            [100, (0, (1, 0, 0), 0), '100'],
            [-100, (1, (1, 0, 0), 0), '-100'],
            ['100', (0, (1, 0, 0), 0), '100'],
            ['-100', (1, (1, 0, 0), 0), '-100'],
            ['12.3456789', (0, (1, 2, 3, 4, 5, 6, 7, 8, 9), -7), '12.3456789'],
            ['123.456789', (0, (1, 2, 3, 4, 5, 6, 7, 8, 9), -6), '123.456789'],
            ['1234.56789', (0, (1, 2, 3, 4, 5, 6, 7, 8, 9), -5), '1234.56789'],
            ['-12.3456789', (1, (1, 2, 3, 4, 5, 6, 7, 8, 9), -7), '-12.3456789'],
            ['-123.456789', (1, (1, 2, 3, 4, 5, 6, 7, 8, 9), -6), '-123.456789'],
            ['-1234.56789', (1, (1, 2, 3, 4, 5, 6, 7, 8, 9), -5), '-1234.56789'],
            ['NaN', (0, (), 'n'), 'NaN'],
            ['-NaN', (1, (), 'n'), '-NaN'],
            ['sNaN', (0, (), 'N'), 'sNaN'],
            ['-sNaN', (1, (), 'N'), '-sNaN'],
            ['Infinity', (0, (0, ), 'F'), 'Infinity'],
            ['-Infinity', (1, (0, ), 'F'), '-Infinity'],
            ['Inf', (0, (0, ), 'F'), 'Infinity'],
            ['-Inf', (1, (0, ), 'F'), '-Infinity'],
        ]
        for data in datum:
            self.assertEqual(tuple(Decimal(data[0]).as_tuple()), data[1])
            self.assertEqual(str(Decimal(data[0])), data[2])


class TestMongo(TestBase, unittest.TestCase):
    host = 'localhost'
    database = 'test_nmongo'
    port = 27017
    use_ssl = False

    def test_index(self):
        self.db.pets.createIndex(
            {'name': 1, 'gender': -1},
            options={'name': 'name1'}
        )
        self.db.pets.createIndex(
            {'name': -1},
            options={'name': 'name2'}
        )
        self.assertIn(
            'name1',
            [idx['name'] for idx in self.db.pets.getIndexes()]
        )
        self.db.pets.dropIndex('name1')
        self.assertTrue('name1' not in [idx['name'] for idx in self.db.pets.getIndexes()])
        self.assertEqual(len(self.db.pets.getIndexes()), 2)

        self.db.pets.dropIndexes()
        self.assertEqual(len(self.db.pets.getIndexes()), 1)

    def test_is_clapped(self):
        self.assertTrue(self.db.pets.stats()['ok'])
        self.db.createCollection('testcapped', {'capped': True, 'size': 1024})
        self.assertTrue(self.db.testcapped.isCapped())

    def test_servr_status(self):
        self.assertTrue(self.db.serverStatus()['ok'])
        self.assertEqual(self.db.stats()['db'], self.database)

    def test_map_reduce(self):
        self.assertTrue(
            self.db.pets.mapReduce(
                "function(){}",             # map
                "function(key, values){}",  # reduce
                {'out': {'inline': 1}}
            )['ok']
        )

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

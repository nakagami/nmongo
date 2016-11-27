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
import unittest
import datetime
import time
import nmongo
try:
    from decimal import Decimal
except ImportError:
    from nmongo import Decimal

class TestMongo(unittest.TestCase):
    host = 'localhost'
    database = 'test'
    port = 27017

    def test_nmongo(self):
        db = nmongo.connect(self.host, self.database,  port=self.port)
        r = db.pets.drop()

        data1 = {
            'name': 'Kitty',
            'gender': 'f',
            'age': 0,
            'species': 'cat'
        }
        if sys.implementation.name != 'micropython':
            data1['birth'] = datetime.datetime(1974, 11, 1, 1, 1)
        data2 = {
            'name': 'Snoopy',
            'gender': 'm',
            'age': 0,
            'species': 'cat'
        }
        data3 = {
            'name': 'Kuri',
            'gender': 'm',
            'age': 0,
            'species': 'ferret'
        }

        # Create
        db.pets.insert(data1)
        db.pets.insert([data2, data3])
        self.assertIn('pets', db.getCollectionNames())


        # index
        db.pets.createIndex(
            {'name': 1, 'gender': -1},
            options={'name': 'named_pets_index'}
        )
        db.pets.createIndex(
            {'name': -1},
            options={'name': 'desc_name_pets_index'}
        )
        self.assertIn(
            'named_pets_index',
            [idx['name'] for idx in db.pets.getIndexes()]
        )
        db.pets.dropIndex('named_pets_index')
        self.assertTrue(not 'named_pets_index' in [idx['name'] for idx in db.pets.getIndexes()])
        self.assertEqual(len(db.pets.getIndexes()), 2)

        db.pets.dropIndexes()
        self.assertEqual(len(db.pets.getIndexes()), 1)

        # collection methods
        self.assertTrue(db.pets.stats()['ok'])
        db.createCollection('testcapped', {'capped': True, 'size': 1024})
        self.assertTrue(db.testcapped.isCapped())

        # database methods
        self.assertTrue(db.serverStatus()['ok'])
        self.assertEqual(db.stats()['db'], self.database)

        # mapReduce
        self.assertTrue(
            db.pets.mapReduce(
                "function(){}",             # map
                "function(key, values){}",  # reduce
                {'out': {'inline':1}}
            )['ok']
        )

        # group
        self.assertTrue(
            db.pets.group(
                {'name':1, 'gender':1},     # key
                "function (c, r) {}",       # reduce
                {},                         # initial
                cond={'gender' : 'm'},
            )['ok']
        )

        # Read
        cur = db.pets.find(projection={'_id': 0})
        self.assertEqual(cur.fetchone(), data1)

        self.assertEqual(db.pets.count(), 3)

        self.assertEqual(set(db.pets.distinct('gender')), set(['m','f']))

        # findAndModify
        prev_data1 = db.pets.findAndModify(
            query={'name': 'Kitty'},
            update={'$inc': {'age': 1}},
        )
        next_data1 = db.pets.findOne({'name': 'Kitty'})
        self.assertEqual(prev_data1['age'] + 1, next_data1['age'])

        # Update
        r = db.pets.update(
            {'name': 'Snoopy'},
            {'name': 'Snoopy', 'gender': 'f', 'age': 10, 'species': 'wolf'}
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['nModified'], 1)
        self.assertEqual(
            db.pets.findOne({'name': 'Snoopy'}, projection={'_id': 0}),
            {'name': 'Snoopy', 'gender': 'f', 'age': 10, 'species': 'wolf'},
        )

        r = db.pets.updateOne(
            {'name': 'Snoopy'},          # query
            {'$set': {'gender': 'm'}, '$inc': {'age': 1}},  # update
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['nModified'], 1)
        self.assertEqual(
            db.pets.findOne({'name': 'Snoopy'}, projection={'_id': 0}),
            {'name': 'Snoopy', 'gender': 'm', 'age': 11, 'species': 'wolf'},
        )

        self.assertEqual(db.pets.count(), 3)
        r = db.pets.updateMany(
            {},                     # query
            {'$inc': {'age': 1}},   # update
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['n'], 3)
        self.assertEqual(r['nModified'], 3)
        r = db.pets.updateMany(
            {'name': {'$eq': 'Kitty'}}, # query
            {'$set': {'gender': 'f'}},  # update
        )
        self.assertTrue(r['ok'])
        self.assertEqual(r['n'], 1)
        self.assertEqual(r['nModified'], 0)


        # Delete
        self.assertEqual(db.pets.count(), 3)
        db.pets.insert(data1)
        self.assertEqual(db.pets.count(), 4)
        self.assertEqual(db.pets.remove({'name': 'Kitty', 'age': 0}), 1)
        self.assertEqual(db.pets.count(), 3)
        self.assertEqual(db.pets.findOneAndDelete({'name': 'Kitty'})['age'], 2)
        self.assertEqual(db.pets.count(), 2)

        # insertOne, insertMany
        db.pets.drop()
        oid = db.pets.insertOne(data1)
        self.assertEqual(
            db.pets.find({'_id': oid}).fetchone()['name'],
            data1['name']
        )
        oids = db.pets.insertMany([data2, data3])
        self.assertEqual(
            db.pets.find({'_id': oids[0]}).fetchone()['name'],
            data2['name']
        )

        db.close()

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

if __name__ == "__main__":
    unittest.main()

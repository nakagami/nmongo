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
import socket
import datetime
import time
import binascii
import decimal
import struct
import random
try:
    import hashlib
except ImportError:
    import uhashlib as hashlib

__version__ = '0.1.0'


class OperationalError(Exception):
    pass


# ------------------------------------------------------------------------------
# BSON format
# http://bsonspec.org/spec.html
class ObjectId:
    def __init__(self, oid):
        if isinstance(oid, str):
            oid = binascii.a2b_hex(oid)
        assert isinstance(oid, bytes) and len(oid) == 12
        self.oid = oid

    def to_bytes(self):
        return self.oid

    def __eq__(self, o):
        return self.to_bytes() == o.to_bytes()

    def __repr__(self):
        return 'ObjectId("%s")' % (binascii.b2a_hex(self.oid).decode('utf-8'), )


class Code:
    def __init__(self, source):
        self.source = source

    def to_bytes(self):
        b = to_cstring(self.source)
        return from_int32(len(b)) + b

    def __str__(self):
        return self.source

    def __eq__(self, o):
        return self.source == o.source

    def __repr__(self):
        return 'Code("%s")' % (self.source,)


def to_cstring(s):
    return s.encode('utf-8') + b'\x00'


def _from_int(n, ln):
    b = bytearray()
    for i in range(ln):
        b.append((n >> (i*8)) & 0xff)
    return bytes(b)


def from_int32(n):
    return _from_int(n, 4)


def from_int64(n):
    return _from_int(n, 8)


def from_decimal(d):
    "from decimal.Decimal to decimal128 binary"
    # TODO:
    return b'\x00\x00\x00\x00\x00\x00\x00\x00'


def to_decimal(b):
    "decimal 128 bytes to decimal.Decimal"
    # TODO:
    return decimal.Decimal('0.0')


def to_uint(b):
    "little endian bytes to unsigned int"
    r = 0
    for n in reversed(b):
        r = r * 256 + n
    return r


def _bson_encode_item(ename, v):
    t = type(v)
    if t == float:
        b = b'\x01' + to_cstring(ename) + struct.pack('d', v)
    elif t == str:
        v = to_cstring(v)
        b = b'\x02' + to_cstring(ename) + from_int32(len(v)) + v
    elif t == dict:
        v = _bson_encode_dict(v) + b'\x00'
        b = b'\x03' + to_cstring(ename) + from_int32(len(v) + 4) + v
    elif t in (list, tuple):
        v = {str(i): v[i] for i in range(len(v))}
        v = _bson_encode_dict(v) + b'\x00'
        b = b'\x04' + to_cstring(ename) + from_int32(len(v) + 4) + v
    elif t == ObjectId:
        b = b'\x07' + to_cstring(ename) + v.to_bytes()
    elif t == int:
        if v < 0x8fffffff:
            b = b'\x10' + to_cstring(ename) + from_int32(v)
        else:
            b = b'\x12' + to_cstring(ename) + from_int64(v)
    elif t == bool:
        v = b'\x01' if v else b'\x00'
        b = b'\x08' + to_cstring(ename) + v
    elif sys.implementation.name != 'micropython' and t == time.struct_time:
        v = from_int64(int(time.mktime(v) * 1000.0))
        b = b'\x09' + to_cstring(ename) + v
    elif sys.implementation.name != 'micropython' and t == datetime.datetime:
        v = from_int64(int(time.mktime(v.timetuple()) * 1000.0))
        b = b'\x09' + to_cstring(ename) + v
    elif v is None:
        b = b'\x0a' + to_cstring(ename)
    elif t == Code:
        b = b'\x0d' + to_cstring(ename) + v.to_bytes()
    elif sys.implementation.name != 'micropython' and t == decimal.Decimal:
        b = b'\x13' + to_cstring(ename) + from_decimal(v)
    else:
        raise TypeError("%s:%s" % (ename, str(t)))

    return b


def _bson_encode_dict(d, first_key=None):
    b = bytearray()
    if first_key:
        b += _bson_encode_item(first_key, d[first_key])
        del d[first_key]
    for k, v in d.items():
        b += _bson_encode_item(k, v)
    return b


def bson_encode(v, first_key=None):
    "from python data to binary"
    b = _bson_encode_dict(v, first_key) + b'\x00'
    return from_int32(len(b) + 4) + b


def _bson_decode_item(t, b):
    if t == 0x01:       # double
        v = struct.unpack('d', b[:8])[0]
        rest = b[8:]
    elif t == 0x02:     # string
        ln = to_uint(b[:4])
        v = b[4:4+ln-1].decode('utf-8')
        rest = b[4+ln:]
    elif t == 0x03:     # embedded document
        v, rest = bson_decode(b)
    elif t == 0x04:     # array
        v = []
        d, rest = bson_decode(b)
        for i in sorted([int(k) for k in d]):
            v.append(d[str(i)])
    elif t == 0x06:
        v = None
        rest = b
    elif t == 0x05:     # binary
        ln = to_uint(b[:4])
        v = b[4:4+ln-1]
        rest = b[4+ln:]
        v, _ = bson_decode(b)
    elif t == 0x07:     # ObjectId
        v = ObjectId(b[:12])
        rest = b[12:]
    elif t == 0x08:     # bool
        v = b[0] != b'\x00'
        rest = b[1:]
    elif t == 0x09:     # time
        if sys.implementation.name == 'micropython':
            v = time.localtime(to_uint(b[:8]) / 1000)
        else:
            v = datetime.datetime.fromtimestamp(to_uint(b[:8]) / 1000)
        rest = b[8:]
    elif t == 0x0a:     # None
        v = None
        rest = b
    elif t == 0x0d:     # JavaScript
        ln = to_uint(b[:4])
        v = Code(b[4:4+ln-1].decode('utf-8'))
        rest = b[4+ln:]
    elif t == 0x10:     # int32
        v = struct.unpack('i', b[:4])[0]
        rest = b[4:]
    elif t == 0x11:     # timestamp
        v = b[:8]
        rest = b[8:]
    elif t == 0x12:     # int64
        v = struct.unpack('q', b[:8])[0]
        rest = b[8:]
    elif t == 0x13:     # decimal128
        v = to_decimal(b[:16])
        rest = b[16:]
    else:
        raise ValueError('Unknown %s:%s' % (hex(t), b))

    return v, rest


def _bson_decode_key_value(b):
    t = b[0]
    i = b[1:].find(b'\x00')
    ename = b[1:i+1].decode('utf-8')
    b = b[i+2:]
    v, b = _bson_decode_item(t, b)

    return ename, v, b


def bson_decode(b):
    "from binary to python data"
    if not b:
        return {}, b''
    ln = to_uint(b[:4])
    rest = b[ln:]
    assert b[ln-1] == 0
    b = b[4:ln-1]
    d = {}
    while b:
        k, v, b = _bson_decode_key_value(b)
        d[k] = v
    return d, rest

# ------------------------------------------------------------------------------
# MongoDB wire protocol
# https://docs.mongodb.com/manual/reference/mongodb-wire-protocol/
# https://docs.mongodb.com/manual/reference/method/
OP_REPLY = 1
OP_MSG = 1000
OP_UPDATE = 2001
OP_INSERT = 2002
OP_QUERY = 2004
OP_GET_MORE = 2005
OP_DELETE = 2006
OP_KILL_CURSORS = 2007
OP_COMMAND = 2010
OP_COMMANDREPLY = 2011
COMMANDS = set([
    # https://docs.mongodb.com/manual/reference/command/
    # Aggregation Commands
    'aggregate',
    'count',
    'distinct',
    'group',
    'mapReduce',
    # Geospatial Commands
    'geoNear',
    'geoSearch',
    # Query and Write Operation Commands
    'find',
    'insert',
    'update',
    'delete',
    'findAndModify',
    'getMore',
    'getLastError',
    'getPrevError',
    'resetError',
    'eval',
    'parallelCollectionScan',
    # Query Plan Cache Commands
    'planCacheListFilters',
    'planCacheSetFilter',
    'planCacheClearFilters',
    'planCacheListQueryShapes',
    'planCacheListPlans',
    'planCacheClear',
    # Authentication Commands
    'logout',
    'authenticate',
    'copydbgetnonce',
    'getnonce',
    'authSchemaUpgrade',
    # User Management Commands
    'createUser',
    'updateUser',
    'dropUser',
    'dropAllUsersFromDatabase',
    'grantRolesToUser',
    'revokeRolesFromUser',
    'usersInfo',
    # Role Management Commands
    'createRole',
    'updateRole',
    'dropRole',
    'dropAllRolesFromDatabase',
    'grantPrivilegesToRole',
    'revokePrivilegesFromRole',
    'grantRolesToRole',
    'revokeRolesFromRole',
    'rolesInfo',
    'invalidateUserCache',
    # Replication Commands
    'replSetFreeze',
    'replSetGetStatus',
    'replSetInitiate',
    'replSetMaintenance',
    'replSetReconfig',
    'replSetStepDown',
    'replSetSyncFrom',
    'resync',
    'applyOps',
    'isMaster',
    'replSetGetConfig',
    # Sharding Commands
    'flushRouterConfig',
    'addShard',
    'cleanupOrphaned',
    'checkShardingIndex',
    'enableSharding',
    'listShards',
    'removeShard',
    'getShardMap',
    'getShardVersion',
    'mergeChunks',
    'setShardVersion',
    'shardCollection',
    'shardingState',
    'unsetSharding',
    'split',
    'splitChunk',
    'splitVector',
    'medianKey',
    'moveChunk',
    'movePrimary',
    'isdbgrid',
    # Instance Administration Commands
    'renameCollection',
    'copydb',
    'dropDatabase',
    'listCollections',
    'drop',
    'create',
    'clone',
    'cloneCollection',
    'cloneCollectionAsCapped',
    'convertToCapped',
    'filemd5',
    'createIndexes',
    'listIndexes',
    'deleteIndexes',    # dropIndexes
    'fsync',
    'clean',
    'connPoolSync',
    'connectionStatus',
    'compact',
    'collMod',
    'reIndex',
    'setParameter',
    'getParameter',
    'repairDatabase',
    'repairCursor',
    'touch',
    'shutdown',
    'logRotate',
    'killOp',
    # Diagnostic Commands
    'availableQueryOptions',
    'buildInfo',
    'collStats',
    'connPoolStats',
    'cursorInfo',
    'dataSize',
    'dbHash',
    'dbStats',
    'diagLogging',
    'driverOIDTest',
    'explain',
    'features',
    'getCmdLineOpts',
    'getLog',
    'hostInfo',
    'isSelf',
    'listCommands',
    'listDatabases',
    'netstat',
    'ping',
    'profile',
    'serverStatus',
    'shardConnPoolStats',
    'top',
    'validate',
    'whatsmyuri',
    # Internal Commands
    'handshake',
    '_recvChunkAbort',
    '_recvChunkCommit',
    '_recvChunkStart',
    '_recvChunkStatus',
    '_replSetFresh',
    'mapreduce.shardedfinish',
    '_transferMods',
    'replSetHeartbeat',
    'replSetGetRBID',
    '_migrateClone',
    'replSetElect',
    'writeBacksQueued',
    'writebacklisten',
    # Auditing Commands
    'logApplicationMessage',
])


def _pack_message(op_code, request, response, body):
    b = from_int32(request) + from_int32(response) + from_int32(op_code) + body
    return from_int32(len(b) + 4) + b


def _command(request_id, database, metadata):
    "Create command packet"
    command_name = set([k for k in metadata]) & COMMANDS
    if 'findAndModify' in command_name:
        command_name = 'findAndModify'
    elif len(command_name) == 1:
        command_name = command_name.pop()
    else:
        raise ValueError('Bad Command:%s' % (metadata, ))
    body = to_cstring(database) + to_cstring(command_name) + bson_encode(metadata, command_name) + bson_encode({})
    return _pack_message(OP_COMMAND, request_id, 0, body)


def _command_reply(data):
    "Parse command reply packet"
    metadata, _ = bson_decode(data)
    return metadata


class MongoCursor:
    def __init__(self, collection, first_batch, next_id, batchSize=None):
        self.collection = collection
        self.batch = first_batch
        self.next_id = next_id
        self.batchSize = batchSize
        self.next_index = 0

    def fetchone(self):
        if self.next_index == len(self.batch):
            r = self.collection._getMore(self.next_id, self.batchSize)
            if r['ok']:
                self.batch = r['cursor']['nextBatch']
                self.next_id = r['cursor']['id']
                self.next_index = 0
            else:
                self.batch = []
                self.next_id = 0
                self.next_index = 0
        if self.next_index < len(self.batch):
            v = self.batch[self.next_index]
            self.next_index += 1
        else:
            v = None
        return v

    def fetchall(self):
        rs = []
        r = self.fetchone()
        while r is not None:
            rs.append(r)
            r = self.fetchone()
        return rs

    def __iter__(self):
        return self

    def __next__(self):
        r = self.fetchone()
        if r is None:
            raise StopIteration()
        return r


class MongoCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def _getMore(self, next_id, batchSize):
        params = {'collection': self.name, 'getMore': next_id}
        if batchSize is not None:
            params['batchSize'] = batchSize
        return self.db.runCommand(params)

    def aggregate(self, cursor={}, pipeline=[]):
        params = {
            'aggregate': self.name,
            'cursor': cursor,
            'pipeline': pipeline,
        }
        r = self.db.runCommand(params)
        if r['ok']:
            return MongoCursor(
                self, r['cursor']['firstBatch'],
                r['cursor']['id'],
            )
        raise OperationalError(r['errmsg'])

    def bulkWrite(self, *args, **kwargs):
        raise NotImplementedError()

    def count(self, query={}, fields={}):
        r = self.db.runCommand({
            'count': self.name,
            'query': query,
            'fields': fields
        })
        if r['ok']:
            return r['n']
        raise OperationalError(r['errmsg'])

    def createIndex(self, keys, options={}):
        index = options.copy()
        index['key'] = keys
        if 'name' not in index:
            es = []
            for k, v in keys.items():
                es.append(k)
                es.append(str(int(v)))
            name = '_'.join(es)
            index['name'] = name

        r = self.db.runCommand({
            'createIndexes': self.name,
            'indexes': [index],
            'ns': '.'.join([self.db.database, self.name]),
        })
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def dataSize(self):
        r = self.stats()
        if r['ok']:
            return r['avgObjSize']
        raise OperationalError(r['errmsg'])

    def deleteOne(self, query):
        return self.remove(self, query, limit=1)

    def deleteMany(self, query):
        return self.remove(self, query, limit=0)

    def distinct(self, key, query={}):
        r = self.db.runCommand({
            'distinct': self.name,
            'key': key,
            'query': query,
        })
        if r['ok']:
            return r['values']
        raise OperationalError(r['errmsg'])

    def drop(self):
        metadata = self.db.runCommand({'drop': self.name})
        return metadata['ok'] == 1.0

    def dropIndex(self, idx_name):
        return self.db.runCommand({'deleteIndexes': self.name, 'index': idx_name})

    def dropIndexes(self):
        return self.dropIndex('*')

    def find(self, query={}, projection=None, batchSize=None):
        params = {
            'find': self.name,
            'filter': query,
        }
        if projection is not None:
            params['projection'] = projection
        if batchSize is not None:
            params['batchSize'] = batchSize
        r = self.db.runCommand(params)
        if r['ok']:
            return MongoCursor(
                self, r['cursor']['firstBatch'],
                r['cursor']['id'],
                batchSize,
            )
        raise OperationalError(r['errmsg'])

    def findAndModify(self, **params):
        bad_keys = set(params.keys()) - set([
            'query', 'sort', 'remove', 'update', 'new', 'fields',
            'upsert', 'bypassDocumentValidation', 'writeConcern'
        ])
        if bad_keys:
            raise ValueError('Invalid Parameter %s' % (bad_keys))
        params['findAndModify'] = self.name
        r = self.db.runCommand(params)
        if r['ok']:
            return r['value']
        raise OperationalError(r['errmsg'])

    def findOne(self, query={}, projection=None):
        params = {
            'find': self.name,
            'filter': query,
            'singleBatch': True,
            'limit': 1,
        }
        if projection is not None:
            params['projection'] = projection
        r = self.db.runCommand(params)
        if r['ok']:
            if len(r['cursor']['firstBatch']) == 1:
                return r['cursor']['firstBatch'][0]
            else:
                return None
        raise OperationalError(r['errmsg'])

    def findOneAndDelete(self, query, options={}):
        params = options.copy()
        params['query'] = query
        params['remove'] = True
        return self.findAndModify(**params)

    def findOneAndReplace(self, query, update, options={}):
        params = options.copy()
        params['query'] = query
        params['update'] = update
        params['upsert'] = True
        params['new'] = True
        return self.findAndModify(**params)

    def findOneAndUpdate(self, query, update, options={}):
        return self.findAndReplace(self, query, update, options)

    def getIndexes(self):
        r = self.db.runCommand({'listIndexes': self.name})
        if r['ok']:
            return r['cursor']['firstBatch']
        raise OperationalError(r['errmsg'])

    def group(self, key, reduce_function, initial, keyf=None, cond=None, finalize=None):
        if not isinstance(reduce_function, Code):
            reduce_function = Code(str(reduce_function))
        if not (keyf is None or isinstance(keyf, Code)):
            keyf = Code(str(keyf))
        if not (finalize is None or isinstance(finalize, Code)):
            finalize = Code(str(finalize))
        g = {
            'ns': self.name,
            'key': key,
            '$reduce': reduce_function,
            'initial': initial,
        }
        if keyf is not None:
            g['keyf'] = keyf
        if cond is not None:
            g['cond'] = cond
        if finalize is not None:
            g['finalize'] = finalize

        r = self.db.runCommand({'group': g})
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def insert(self, documents):
        if not isinstance(documents, list):
            documents = [documents]
        r = self.db.runCommand({
            'insert': self.name,
            'documents': documents,
        })
        if r['ok']:
            return r['n']
        raise OperationalError(r['errmsg'])

    def insertOne(self, document):
        return self.insertMany([document])[0]

    def insertMany(self, documents):
        for d in documents:
            if '_id' not in d:
                d['_id'] = self.db.genObjectId()
        r = self.db.runCommand({
            'insert': self.name,
            'documents': documents,
        })
        if r['ok']:
            return [d['_id'] for d in documents]
        raise OperationalError(r['errmsg'])

    def isCapped(self):
        r = self.db.runCommand({
            'listCollections': 1.0,
            'filter': {'name': self.name},
        })
        if r['ok']:
            return r['cursor']['firstBatch'][0]['options']['capped']
        raise OperationalError(r['errmsg'])

    def mapReduce(self, map_function, reduce_function, options):
        if not isinstance(map_function, Code):
            map_function = Code(str(map_function))
        if not isinstance(reduce_function, Code):
            reduce_function = Code(str(reduce_function))
        params = options.copy()
        params['mapReduce'] = self.name
        params['map'] = map_function
        params['reduce'] = reduce_function
        r = self.db.runCommand(params)
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def reIndex(self):
        r = self.db.runCommand({'reIndex': self.name})
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def replaceOne(self, query, update, options={}):
        params = options.copy()
        params['multi'] = True
        if 'upsert' not in params:
            params['upsert'] = False
        return self.update(query, update, params)

    def remove(self, query, limit=0):
        r = self.db.runCommand({
            'delete': self.name,
            'deletes': [{'q': query, 'limit': limit}],
        })
        if r['ok']:
            return r['n']
        raise OperationalError(r['errmsg'])

    def renameCollection(self, new_name):
        r = self.db.runCommand({
            'renameCollection': '.'.join([self.db.database, self.name]),
            'dropTarget': None,
            'to': '.'.join([self.db.database, new_name])
        })
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def save(self, document):
        if '_id' not in document:
            r = self.insert(document)
        else:
            query = {'_id': document['_id']}
            params = document.copy()
            del params['_id']
            r = self.update(query, params, {'multi': True, 'upsert': True})
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def stats(self, options=None):
        params = {'collStats': self.name}
        if options is not None:
            params['options'] = options
        return self.db.runCommand(params)

    def storageSize(self):
        r = self.stats()
        if r['ok']:
            return r['storageSize']
        raise OperationalError(r['errmsg'])

    def totalSize(self):
        r = self.stats()
        if r['ok']:
            return r['totalIndexSize'] + r['storageSize']
        raise OperationalError(r['errmsg'])

    def totalIndexSize(self):
        r = self.stats()
        if r['ok']:
            return r['totalIndexSize']
        raise OperationalError(r['errmsg'])

    def update(self, query, update, options={}):
        params = options.copy()
        if 'upsert' not in params:
            params['upsert'] = False
        if 'multi' not in params:
            params['multi'] = False
        params['q'] = query
        params['u'] = update
        r = self.db.runCommand({
            'update': self.name,
            'updates': [params],
        })
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def updateOne(self, query, update, options={}):
        params = options.copy()
        params['upsert'] = True
        params['multi'] = True
        r = self.update(query, update, params)
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def updateMany(self, query, update, options={}):
        params = options.copy()
        params['upsert'] = True
        params['multi'] = True
        r = self.update(query, update, params)
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def validate(self, full=None):
        r = self.db.runCommand({
            'validate': self.name,
            'full': full,
        })
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])


class MongoDatabase:
    def _get_machine_id_bytes(self):
        sha1 = hashlib.sha1()
        sha1.update(self.runCommand({'whatsmyuri': 1})['you'].encode('utf-8'))
        return sha1.digest()[:3]

    def _get_time_bytes(self):
        return bytes(reversed(from_int32(int(time.time()))))

    def __init__(self, host, database, port=27017):
        self.host = host
        self.database = database
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))
        self._request_id = 0

        if sys.implementation.name != 'micropython':
            self._object_id_counter = random.randrange(0, 0xffffff)
        else:
            sha1 = hashlib.sha1()
            sha1.update(self._get_time_bytes())
            self._object_id_counter = to_uint(sha1.digest()[:3])
        self._process_id_bytes = bytes(reversed(from_int32(os.getpid())[:2]))
        self._machine_id_bytes = self._get_machine_id_bytes()

    def _send(self, b):
        n = 0
        while (n < len(b)):
            n += self._sock.send(b[n:])

    def _recv(self, ln):
        r = b''
        while len(r) < ln:
            b = self._sock.recv(ln-len(r))
            if not b:
                raise socket.error("Can't recv packets")
            r += b
        return r

    def __getattr__(self, name):
        if name[0] == '_':
            raise AttributeError
        return MongoCollection(self, name)

    def genObjectId(self):
        self._object_id_counter = (self._object_id_counter + 1) & 0xffffff
        return ObjectId(
            self._get_time_bytes() +
            self._machine_id_bytes +
            self._process_id_bytes +
            bytes(reversed(from_int32(self._object_id_counter)[:3]))
        )

    def commandHelp(self, name):
        r = self.runCommand({'help': 1.0, name: 1.0})
        if r['ok']:
            return r['help']
        raise OperationalError(r['errmsg'])

    def createCollection(self, name, options={}):
        params = options.copy()
        params['create'] = name
        return self.runCommand(params)

    def dropDatabase(self):
        return self.runCommand({'dropDatabase': 1.0})

    def getCollectionInfos(self):
        r = self.runCommand({'listCollections': 1.0})
        if r['ok']:
            return r['cursor']['firstBatch']
        raise OperationalError(r['errmsg'])

    def getCollectionNames(self):
        return [r['name'] for r in self.getCollectionInfos()]

    def getLastError(self):
        return self.getLastErrorObj()['err']

    def getLastErrorObj(self):
        return self.runCommand({'getlasterror': 1.0})

    def getLogComponents(self):
        r = self.runCommand({'getParameter': 1.0, 'logComponentVerbosity': 1.0})
        if r['ok']:
            return r['cursor']['logComponentVerbosity']
        raise OperationalError(r['errmsg'])

    def getPrevError(self):
        return self.runCommand({'getpreverror': 1.0})

    def hostInfo(self):
        r = self.runCommand({'hostInfo': 1.0})
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def isMaster(self):
        return self.runCommand({'isMaster': 1.0})

    def listCommands(self):
        return self.runCommand({'listCommands': 1.0})

    def repairDatabase(self):
        r = self.runCommand({'repairDatabase': 1.0})
        if r['ok']:
            return r
        raise OperationalError(r['errmsg'])

    def runCommand(self, metadata, database=None):
        if database is None:
            database = self.database
        self._send(_command(self._request_id, database, metadata))
        self._request_id += 1

        head = self._recv(16)
        ln = to_uint(head[0:4])
        # request_id = to_uint(head[4:8])
        # response_id = to_uint(head[8:12])
        opcode = to_uint(head[12:16])
        assert opcode == OP_COMMANDREPLY
        data = self._recv(ln - 16)
        return _command_reply(data)

    def serverBuildInfo(self):
        return self.runCommand({'buildInfo': 1.0})

    def serverStatus(self):
        return self.runCommand({'serverStatus': 1.0})

    def stats(self, scale=None):
        return self.runCommand({'dbStats': 1.0, 'scale': scale})

    def version(self):
        return self.serverBuildInfo()['version']

    def close(self):
        self._sock.close()


def connect(host, database, port=27017):
    return MongoDatabase(host, database, port)

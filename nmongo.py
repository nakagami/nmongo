###############################################################################
# MIT License
#
# Copyright (c) 2016-2018 Hajime Nakagami
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
import struct
import random
try:
    import hashlib
except ImportError:
    import uhashlib as hashlib


__version__ = '0.4.1'


try:
    from decimal import Decimal
except ImportError:
    # Internal Decimal class for micropython
    from ucollections import namedtuple
    DecimalTuple = namedtuple('DecimalTuple', ['sign', 'digits', 'exponent'])

    class Decimal:
        def _int_to_tuple(self, v):
            if v < 0:
                sign = 1
                v *= -1
            else:
                sign = 0
            digits = []
            if v != 0:
                while v != 0:
                    digits.append(v % 10)
                    v //= 10
                digits.reverse()
                digits = tuple(digits)
            else:
                digits = (0, )
            exponent = 0
            return sign, digits, exponent

        def __init__(self, v):
            if isinstance(v, str):
                t = {
                    'NaN': (0, (), 'n'),
                    '-NaN': (1, (), 'n'),
                    'sNaN': (0, (), 'N'),
                    '-sNaN': (1, (), 'N'),
                    'Infinity': (0, (0, ), 'F'),
                    '-Infinity': (1, (0, ), 'F'),
                    'Inf': (0, (0, ), 'F'),
                    '-Inf': (1, (0, ), 'F'),
                }.get(v)
                if t:
                    sign, digits, exponent = t
                else:
                    if (len(v) == 0) or (v[0] == '-' and len(v) == 1):
                        raise ValueError("Decimal(%s)" % (v, ))
                    if v[0] == '-':
                        sign = 1
                        v = v[1:]
                    else:
                        sign = 0
                    i = v.find('.')
                    if i < 0:
                        s = v
                        exponent = 0
                    else:
                        s = v[:i] + v[i+1:]
                        exponent = (len(s) - i) * -1
                    _, digits, _ = self._int_to_tuple(int(s))
            elif isinstance(v, int):
                sign, digits, exponent = self._int_to_tuple(v)
            elif isinstance(v, float):
                pass
            elif isinstance(v, tuple):
                sign, digits, exponent = v
            else:
                raise TypeError("Cannot convert %r to Decimal" % (v,))

            self.sign = sign
            self.digits = digits
            self.exponent = exponent

        def as_tuple(self):
            return DecimalTuple(self.sign, self.digits, self.exponent)

        def __eq__(self, v):
            return self.as_tuple() == v.as_tuple()

        def __repr__(self):
            return "Decimal('%s')" % (self.__str__(), )

        def __str__(self):
            s = {
                (0, (), 'n'): 'NaN',
                (1, (), 'n'): '-NaN',
                (0, (), 'N'): 'sNaN',
                (1, (), 'N'): '-sNaN',
                (0, (0,), 'F'): 'Infinity',
                (1, (0,), 'F'): '-Infinity',
            }.get((self.sign, self.digits, self.exponent))
            if s:
                return s
            n = 0
            for i in self.digits:
                n = n * 10 + i
            s = str(n)
            if self.sign:
                s = '-' + s
            if self.exponent > 0:
                s += '0' * self.exponent
            elif self.exponent < 0:
                s = s[:self.exponent] + '.' + s[self.exponent:]
            return s


def _bytes_to_big_uint(b):
    "Convert from big endian bytes to uint."
    r = 0
    for n in b:
        r = r * 256 + n
    return r


def _uint_to_bytes(val, ln):
    "Convert int value to little endian bytes."
    a = []
    for _ in range(ln):
        a.append(val & 0xff)
        val >>= 8
    return bytes(a)


def _md5_hexdigest(message):
    """import hashlib; return hashlib.md5(message).hexdigest()
    support only less than 56 bytes"""
    assert len(message) < 56

    def _bit_not(n): return ((1 << 32) - 1 - n) & 0xffffffff
    def F(x,y,z):   return (z ^ (x & (y ^ z))) & 0xffffffff
    def G(x,y,z):   return (y ^ (z & (y ^ x))) & 0xffffffff
    def H(x,y,z):   return (x ^ y ^ z) & 0xffffffff
    def I(x,y,z):   return (y ^ (x | _bit_not(z))) & 0xffffffff
    def ROTATE_LEFT(x, n): return ((x << n) | (x >> (32-n))) & 0xffffffff
    def FF(a, b, c, d, x, s, ac):
        a = (a + F(b, c, d) + x + ac) & 0xffffffff
        a = (ROTATE_LEFT(a, s) + b) & 0xffffffff
        return a
    def GG(a, b, c, d, x, s, ac):
        a = (a + G(b, c, d) + x + ac) & 0xffffffff
        a =  (ROTATE_LEFT(a, s) + b) & 0xffffffff
        return a
    def HH(a, b, c, d, x, s, ac):
        a = (a + H(b, c, d) + x + ac) & 0xffffffff
        a = (ROTATE_LEFT(a, s) + b) & 0xffffffff
        return a
    def II(a, b, c, d, x, s, ac):
        a = (a + I(b, c, d) + x + ac) & 0xffffffff
        a = (ROTATE_LEFT(a, s) + b) & 0xffffffff
        return a

    message_len = len(message)
    data = message + b'\x80' + b'\00' * (55 - message_len) + _uint_to_bytes(message_len*8, 4) + b'\x00\x00\x00\x00'
    W = [to_uint(b) for b in zip(*[iter(data)]*4)]
    assert len(W) == 16

    a0 = a = 0x67452301
    b0 = b = 0xefcdab89
    c0 = c = 0x98badcfe
    d0 = d = 0x10325476

    a = FF(a,b,c,d,W[0],7,0xd76aa478)
    d = FF(d,a,b,c,W[1],12,0xe8c7b756)
    c = FF(c,d,a,b,W[2],17,0x242070db)
    b = FF(b,c,d,a,W[3],22,0xc1bdceee)
    a = FF(a,b,c,d,W[4],7,0xf57c0faf)
    d = FF(d,a,b,c,W[5],12,0x4787c62a)
    c = FF(c,d,a,b,W[6],17,0xa8304613)
    b = FF(b,c,d,a,W[7],22,0xfd469501)
    a = FF(a,b,c,d,W[8],7,0x698098d8)
    d = FF(d,a,b,c,W[9],12,0x8b44f7af)
    c = FF(c,d,a,b,W[10],17,0xffff5bb1)
    b = FF(b,c,d,a,W[11],22,0x895cd7be)
    a = FF(a,b,c,d,W[12],7,0x6b901122)
    d = FF(d,a,b,c,W[13],12,0xfd987193)
    c = FF(c,d,a,b,W[14],17,0xa679438e)
    b = FF(b,c,d,a,W[15],22,0x49b40821)

    a = GG(a,b,c,d,W[1],5,0xf61e2562)
    d = GG(d,a,b,c,W[6],9,0xc040b340)
    c = GG(c,d,a,b,W[11],14,0x265e5a51)
    b = GG(b,c,d,a,W[0],20,0xe9b6c7aa)
    a = GG(a,b,c,d,W[5],5,0xd62f105d)
    d = GG(d,a,b,c,W[10],9,0x02441453)
    c = GG(c,d,a,b,W[15],14,0xd8a1e681)
    b = GG(b,c,d,a,W[4],20,0xe7d3fbc8)
    a = GG(a,b,c,d,W[9],5,0x21e1cde6)
    d = GG(d,a,b,c,W[14],9,0xc33707d6)
    c = GG(c,d,a,b,W[3],14,0xf4d50d87)
    b = GG(b,c,d,a,W[8],20,0x455a14ed)
    a = GG(a,b,c,d,W[13],5,0xa9e3e905)
    d = GG(d,a,b,c,W[2],9,0xfcefa3f8)
    c = GG(c,d,a,b,W[7],14,0x676f02d9)
    b = GG(b,c,d,a,W[12],20,0x8d2a4c8a)

    a = HH(a,b,c,d,W[5],4,0xfffa3942)
    d = HH(d,a,b,c,W[8],11,0x8771f681)
    c = HH(c,d,a,b,W[11],16,0x6d9d6122)
    b = HH(b,c,d,a,W[14],23,0xfde5380c)
    a = HH(a,b,c,d,W[1],4,0xa4beea44)
    d = HH(d,a,b,c,W[4],11,0x4bdecfa9)
    c = HH(c,d,a,b,W[7],16,0xf6bb4b60)
    b = HH(b,c,d,a,W[10],23,0xbebfbc70)
    a = HH(a,b,c,d,W[13],4,0x289b7ec6)
    d = HH(d,a,b,c,W[0],11,0xeaa127fa)
    c = HH(c,d,a,b,W[3],16,0xd4ef3085)
    b = HH(b,c,d,a,W[6],23,0x04881d05)
    a = HH(a,b,c,d,W[9],4,0xd9d4d039)
    d = HH(d,a,b,c,W[12],11,0xe6db99e5)
    c = HH(c,d,a,b,W[15],16,0x1fa27cf8)
    b = HH(b,c,d,a,W[2],23,0xc4ac5665)

    a = II(a,b,c,d,W[0],6,0xf4292244)
    d = II(d,a,b,c,W[7],10,0x432aff97)
    c = II(c,d,a,b,W[14],15,0xab9423a7)
    b = II(b,c,d,a,W[5],21,0xfc93a039)
    a = II(a,b,c,d,W[12],6,0x655b59c3)
    d = II(d,a,b,c,W[3],10,0x8f0ccc92)
    c = II(c,d,a,b,W[10],15,0xffeff47d)
    b = II(b,c,d,a,W[1],21,0x85845dd1)
    a = II(a,b,c,d,W[8],6,0x6fa87e4f)
    d = II(d,a,b,c,W[15],10,0xfe2ce6e0)
    c = II(c,d,a,b,W[6],15,0xa3014314)
    b = II(b,c,d,a,W[13],21,0x4e0811a1)
    a = II(a,b,c,d,W[4],6,0xf7537e82)
    d = II(d,a,b,c,W[11],10,0xbd3af235)
    c = II(c,d,a,b,W[2],15,0x2ad7d2bb)
    b = II(b,c,d,a,W[9],21,0xeb86d391)

    a = (a0 + a) & 0xffffffff
    b = (b0 + b) & 0xffffffff
    c = (c0 + c) & 0xffffffff
    d = (d0 + d) & 0xffffffff

    return binascii.hexlify(
        _uint_to_bytes(a, 4) +
        _uint_to_bytes(b, 4) +
        _uint_to_bytes(c, 4) +
        _uint_to_bytes(d, 4)
    ).decode('utf-8')


def hmac_sha1_digest(key, msg):
    if sys.implementation.name == 'micropython':
        def translate(d, t):
            return bytes(t[x] for x in d)
        trans_5C = bytes((x ^ 0x5C) for x in range(256))
        trans_36 = bytes((x ^ 0x36) for x in range(256))

        outer = hashlib.sha1()
        inner = hashlib.sha1()
        digest_size = 20
        blocksize = 64

        if len(key) > blocksize:
            key = hashlib.sha1(key).digest()

        key = key + bytes(blocksize - len(key))
        outer.update(translate(key, trans_5C))
        inner.update(translate(key, trans_36))
        inner.update(msg)
        outer.update(inner.digest())
        return outer.digest()
    else:
        import hmac
        return hmac.HMAC(key, msg, hashlib.sha1).digest()


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


def from_int16(n):
    return _from_int(n, 2)


def from_int32(n):
    return _from_int(n, 4)


def from_int64(n):
    return _from_int(n, 8)


def from_int112(n):
    return _from_int(n, 14)


def from_decimal(d):
    "from Decimal to decimal128 binary"
    sign, digits, exponent = d.as_tuple()
    v = {
        (0, (), 'n'): b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00|',         # NaN
        (1, (), 'n'): b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfc',      # -NaN
        (0, (), 'N'): b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~',         # sNaN
        (1, (), 'N'): b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xfe',      # -sNaN
        (0, (0, ), 'F'): b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00x',      # Infinity
        (1, (0, ), 'F'): b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf8',   # -Infinity
    }.get((sign, digits, exponent))
    if v:
        return v
    num = 0
    for n in digits:
        num = num * 10 + n
    fraction = from_int112(num)
    if fraction[-1] & 0b00100000:
        exponent = (exponent + 6176) // 2
    else:
        exponent = (exponent + 6176) * 2
    exponent = from_int16(exponent)
    if sign:
        exponent = bytes([exponent[0], exponent[1] | 0x80])

    return fraction + exponent


def to_decimal(b):
    "decimal 128 bytes to Decimal"
    sign = 1 if (b[-1] & 0x80) else 0
    if (b[-1] & 0x60) == 0x60:
        exponent = to_uint(bytes([b[-2], b[-1] & 0x1f])) * 2 - 6176
    else:
        exponent = to_uint(bytes([b[-2], b[-1] & 0x7f])) // 2 - 6176
    digits = to_uint(b[:-2])
    v = {
        (0, 0, 8160): Decimal('NaN'),
        (1, 0, 8160): Decimal('-NaN'),
        (0, 0, 9184): Decimal('sNaN'),
        (1, 0, 9184): Decimal('-sNaN'),
        (0, 0, 6112): Decimal('Infinity'),
        (1, 0, 6112): Decimal('-Infinity'),
    }.get((sign, digits, exponent))
    if v:
        return v
    return Decimal((sign, Decimal(digits).as_tuple()[1], exponent))


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
        v = _bson_encode_list(v) + b'\x00'
        b = b'\x04' + to_cstring(ename) + from_int32(len(v) + 4) + v
    elif t in (bytes, ):
        b = b'\x05' + to_cstring(ename) + from_int32(len(v)) + b'\x00' + v
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
    elif t == Decimal:
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


def _bson_encode_list(a):
    b = bytearray()
    for i in range(len(a)):
        b += _bson_encode_item(str(i), a[i])
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
        # assert b[4] == 0    # Generic binary subtype
        v = b[5:5+ln]
        rest = b[5+ln:]
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
    'balancerStart',
    'balancerStatus',
    'balancerStop',
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
    'addShardToZone',
    'removeShardFromZone',
    'updateZoneKeyRange',
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
    'setFeatureCompatibilityVersion',
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
    'saslStart',
    'saslContinue',
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

    def __init__(self, host, database, user, password, port, use_ssl, ssl_ca_certs):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))
        if use_ssl:
            import ssl
            if ssl_ca_certs:
                self._sock = ssl.wrap_socket(self._sock, ca_certs=ssl_ca_certs)
            else:
                self._sock = ssl.wrap_socket(self._sock)

        self._request_id = 0

        if sys.implementation.name != 'micropython':
            self._object_id_counter = random.randrange(0, 0xffffff)
        else:
            sha1 = hashlib.sha1()
            sha1.update(self._get_time_bytes())
            self._object_id_counter = to_uint(sha1.digest()[:3])
        self._process_id_bytes = bytes(reversed(from_int32(os.getpid())[:2]))

        if self.user:
            self.auth(self.user, self.password)

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

    def auth(self, user, password):
        # https://github.com/mongodb/specifications/blob/master/source/auth/auth.rst#scram-sha-1
        import base64

        printable = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/'
        nonce = ''.join(printable[random.randrange(0, len(printable))] for i in range(32))
        r = self.runCommand({
            'saslStart': 1.0,
            'mechanism': 'SCRAM-SHA-1',
            'payload': ('n,,n=%s,r=%s' % (user, nonce)).encode('utf-8'),
        }, database='admin')
        if not r['ok']:
            raise OperationalError(r['errmsg'])
        reply_payload = {s[0]: s[2:] for s in r['payload'].decode('utf-8').split(',')}
        reply_payload['i'] = int(reply_payload['i'])
        assert reply_payload['r'][:len(nonce)] == nonce

        if hasattr(hashlib, "md5"):
            m = hashlib.md5()
            m.update((user + ':mongo:' + password).encode('utf-8'))
            password = m.hexdigest()
        else:
            password = _md5_hexdigest((user + ':mongo:' + password).encode('utf-8'))

        # calc salted_pass
        if sys.implementation.name == 'micropython':
            _u1 = hmac_sha1_digest(
                password.encode('utf-8'),
                base64.standard_b64decode(reply_payload['s']) + b'\x00\x00\x00\x01'
            )
            _ui = _bytes_to_big_uint(_u1)
            for _ in range(reply_payload['i'] - 1):
                _u1 = hmac_sha1_digest(password.encode('utf-8'), _u1)
                _ui ^= _bytes_to_big_uint(_u1)
            # 20 is sha1 hash size
            salted_pass = _uint_to_bytes(_ui, 20)
            # reverse (little to big endian)
            salted_pass = bytes(reversed(bytearray(salted_pass)))
        else:
            salted_pass = hashlib.pbkdf2_hmac(
                'sha1',
                password.encode('utf-8'),
                base64.standard_b64decode(reply_payload['s']),
                reply_payload['i'],
            )

        client_key = hmac_sha1_digest(salted_pass, b"Client Key")
        auth_msg = b"n=%s,r=%s,%s,c=biws,r=%s" % (
            user.encode('utf-8'),
            nonce.encode('utf-8'),r['payload'],
            reply_payload['r'].encode('utf-8'),
        )
        client_sig = hmac_sha1_digest(hashlib.sha1(client_key).digest(), auth_msg)
        proof = base64.standard_b64encode(
            b"".join([bytes([x ^ y]) for x, y in zip(client_key, client_sig)])
        )
        payload = ("c=biws,r=%s,p=" % reply_payload['r']).encode('utf-8') + proof

        k = hmac_sha1_digest(salted_pass, b"Server Key")
        server_sig = base64.standard_b64encode(hmac_sha1_digest(k, auth_msg)).decode('utf-8')

        r = self.runCommand({
            'saslContinue': 1.0,
            'conversationId': r['conversationId'],
            'payload': payload,
        }, database='admin')
        if not r['ok']:
            raise OperationalError(r['errmsg'])
        reply_payload = {s[0]: s[2:] for s in r['payload'].decode('utf-8').split(',')}

        assert reply_payload['v'] == server_sig

        if not r['done']:
            r = self.runCommand({
                'saslContinue': 1.0,
                'conversationId': r['conversationId'],
                'payload': b'',
            }, database='admin')
            if not r['ok']:
                raise OperationalError(r['errmsg'])

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

    def createView(self, viewname, collectionname, pipeline, collation=None):
        params = {}
        params['create'] = viewname
        params['viewOn'] = collectionname
        params['pipeline'] = pipeline
        if collation is not None:
            params['collation'] = collation
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

    def getCollection(self, name):
        if name in self.getCollectionNames():
            return MongoCollection(self, name)
        raise OperationalError("'%s' is not collection name" % (name, ))

    def getCollections(self):
        return [MongoCollection(self, name) for name in self.getCollectionNames()]

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


def connect(host, database, user=None, password='', port=27017, use_ssl=False, ssl_ca_certs=None):
    return MongoDatabase(host, database, user, password, port, use_ssl, ssl_ca_certs)

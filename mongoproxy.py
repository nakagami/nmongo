#!/usr/bin/env python3
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
import binascii
import nmongo


def recv_from_sock(sock, nbytes):
    n = nbytes
    recieved = b''
    while n:
        bs = sock.recv(n)
        recieved += bs
        n -= len(bs)
    return recieved


def print_message(s, opcode, request, response, body):
    print('%s:%d' % (s, opcode), end='')
    if opcode == 2004:      # OP_QUERY
        flag = int.from_bytes(body[0:4], byteorder='little')
        i = body[4:].find(b'\x00')
        collection = body[4:i+4].decode('utf-8')
        skip = int.from_bytes(body[i+5:i+9], byteorder='little')
        num_return = int.from_bytes(body[i+9:i+13], byteorder='little')
        query, selector = nmongo.bson_decode(body[i+13:])
        print("\tflag=%d,collection=%s,skip=%d,num_return=%d,query=%s,selector=%s" % (
            flag, collection, skip, num_return, query, selector
        ))
    elif opcode == 1:       # OP_REPLY
        flag = int.from_bytes(body[0:4], byteorder='little')
        cursor = int.from_bytes(body[4:12], byteorder='little')
        start = int.from_bytes(body[12:16], byteorder='little')
        num_return = int.from_bytes(body[16:20], byteorder='little')
        doc, _ = nmongo.bson_decode(body[20:])
        print("\tflag=%d,cursor=%d,start=%d,num_return=%d,doc=%s" % (
            flag, cursor, start, num_return, doc
        ))
    elif opcode == 2010:    # OP_COMMAND
        i = body.find(b'\x00')
        database = body[:i].decode('utf-8')
        b = body[i+1:]
        i = b.find(b'\x00')
        command = b[:i].decode('utf-8')
        b = b[i+1:]
        metadata, b = nmongo.bson_decode(b)
        args, input_docs = nmongo.bson_decode(b)
        assert args == {}
        assert input_docs == b''
        print("\tdatabase=%s,command=%s,metadata=%s" % (
            database, command, metadata
        ))
    elif opcode == 2011:    # OP_COMMANDREPLY
        metadata, b = nmongo.bson_decode(body)
        reply, b = nmongo.bson_decode(b)
        output, _ = nmongo.bson_decode(b)
        assert reply == output == {}
        print("\tmetadata=%s" % (metadata,))
    else:
        print(body)


def proxy_wire(server_name, server_port, listen_host, listen_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((listen_host, listen_port))
    sock.listen(1)
    client_sock, addr = sock.accept()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.connect((server_name, server_port))

    while True:
        client_head = recv_from_sock(client_sock, 16)
        ln = int.from_bytes(client_head[0:4], byteorder='little')
        request = int.from_bytes(client_head[4:8], byteorder='little')
        response = int.from_bytes(client_head[8:12], byteorder='little')
        opcode = int.from_bytes(client_head[12:16], byteorder='little')
        client_body = recv_from_sock(client_sock, ln-16)
        print_message('C->S', opcode, request, response, client_body)
        server_sock.send(client_head)
        server_sock.send(client_body)

        server_head = recv_from_sock(server_sock, 16)
        ln = int.from_bytes(server_head[0:4], byteorder='little')
        request = int.from_bytes(server_head[4:8], byteorder='little')
        response = int.from_bytes(server_head[8:12], byteorder='little')
        opcode = int.from_bytes(server_head[12:16], byteorder='little')
        server_body = recv_from_sock(server_sock, ln-16)
        print_message('S->C', opcode, request, response, server_body)
        client_sock.send(server_head)
        client_sock.send(server_body)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage : ' + sys.argv[0] + ' server[:port] [listen_host:]listen_port')
        sys.exit()

    server = sys.argv[1].split(':')
    server_name = server[0]
    if len(server) == 1:
        server_port = 27017
    else:
        server_port = int(server[1])

    listen = sys.argv[2].split(':')
    if len(listen) == 1:
        listen_host = 'localhost'
        listen_port = int(listen[0])
    else:
        listen_host = listen[0]
        listen_port = int(listen[1])

    proxy_wire(server_name, server_port, listen_host, listen_port)

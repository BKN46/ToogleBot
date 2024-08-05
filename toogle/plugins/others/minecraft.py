'''
Copyright (C) 2015 Barnaby Gale

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies of the Software and its documentation and acknowledgment shall be
given in the documentation and software packages that this Software was
used.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

import argparse
import collections
import re
import socket
import struct
import sys

bufsize = 4096

Packet = collections.namedtuple("Packet", ("ident", "kind", "payload"))


class IncompletePacket(Exception):
    def __init__(self, minimum):
        self.minimum = minimum

class MCRCON:
    @staticmethod
    def decode_packet(data):
        if len(data) < 14:
            raise IncompletePacket(14)

        length = struct.unpack("<i", data[:4])[0] + 4
        if len(data) < length:
            raise IncompletePacket(length)

        ident, kind = struct.unpack("<ii", data[4:12])
        payload, padding = data[12:length-2], data[length-2:length]
        assert padding == b"\x00\x00"
        return Packet(ident, kind, payload), data[length:]


    @staticmethod
    def encode_packet(packet):
        data = struct.pack("<ii", packet.ident, packet.kind) + packet.payload + b"\x00\x00"
        return struct.pack("<i", len(data)) + data


    @staticmethod
    def receive_packet(sock):
        data = b""
        while True:
            try:
                return MCRCON.decode_packet(data)[0]
            except IncompletePacket as exc:
                while len(data) < exc.minimum:
                    data += sock.recv(exc.minimum - len(data))


    @staticmethod
    def send_packet(sock, packet):
        sock.sendall(MCRCON.encode_packet(packet))


    @staticmethod
    def login(sock, password):
        try:
            MCRCON.send_packet(sock, Packet(0, 3, password.encode("utf8")))
            packet = MCRCON.receive_packet(sock)
        except Exception as e:
            return False
        return packet.ident == 0


    @staticmethod
    def command(sock, text):
        MCRCON.send_packet(sock, Packet(0, 2, text.encode("utf8")))
        MCRCON.send_packet(sock, Packet(1, 0, b""))
        response = b""
        while True:
            packet = MCRCON.receive_packet(sock)
            if packet.ident != 0:
                break
            response += packet.payload
        return response.decode("utf8")
    
    
    @staticmethod
    def send_single(host, port, password, cmd):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        # Log in
        result = MCRCON.login(sock, password)
        if not result:
            raise Exception("RCON login failed")
        try:
            response = MCRCON.command(sock, cmd)
        except Exception as e:
            raise Exception("RCON command failed")
        sock.close()
        response = re.sub(r"§.{1}", "", response)
        return response


    def __init__(self, host, port, password):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        # Log in
        result = MCRCON.login(self.sock, password)
        if not result:
            raise Exception("RCON login failed")


    def send(self, command):
        response = MCRCON.command(self.sock, command)
        response = re.sub(r"§.{1}", "", response)
        return response


    def __del__(self):
        self.sock.close()

if __name__ == '__main__':
    res = MCRCON.send_single(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
    print(res)

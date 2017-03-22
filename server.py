#! /usr/bin/env python

import os
import sys
import socketserver


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        # self.data = self.rfile.readline().strip()
        print("Sending file....")
        self.request.sendall(bytes("main.js", 'utf-8'))
        ack = self.request.recv(2048)
        assert ack == b'OK'
        print(ack)
        # if ack == b'OK':
        with open('main.js', 'rb') as fp:
            size = os.fstat(fp.fileno()).st_size
            self.request.sendall(bytes(size))
            buf = fp.read(1024)
            while buf:
                self.request.sendall(buf)
                buf = fp.read(1024)


if __name__ == '__main__':
    HOST, PORT = '0.0.0.0', 13000
    with socketserver.TCPServer((HOST, PORT), TCPHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        print("Running on: " + HOST)
        server.serve_forever()

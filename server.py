#! /usr/bin/env python

import os
import socketserver
import os.path as osp


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        # self.data = self.rfile.readline().strip()
        req = self.request.recv(2048)
        print(req)
        if req == b'FILE_LIST':
            self.list_files()

    def send_file(self, file):
        print("Sending file....")
        self.request.sendall(bytes("main.js", 'utf-8'))
        ack = self.request.recv(2048)
        assert ack == b'OK'
        print(ack)
        # if ack == b'OK':
        with open('main.js', 'rb') as fp:
            size = os.fstat(fp.fileno()).st_size
            self.request.sendall(bytes(str(size), 'utf-8'))
            buf = fp.read(1024)
            while buf:
                self.request.sendall(buf)
                buf = fp.read(1024)

    def list_files(self):
        print("Listing files...")
        for path, dirs, files in os.walk('./files'):
            for f in files:
                print(f)
                file_path = osp.join(path, f)
                size = os.stat(file_path).st_size
                resp = '{0},{1}'.format(f, size)
                self.request.sendall(bytes(str(resp), 'utf-8'))
                ack = self.request.recv(2048)
                assert ack == b'OK'
        self.request.sendall(b'END')


if __name__ == '__main__':
    HOST, PORT = '0.0.0.0', 12000
    server = socketserver.TCPServer((HOST, PORT), TCPHandler)
    try:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        print("Running on: " + HOST)
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

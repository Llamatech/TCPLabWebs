#! /usr/bin/env python

import os
import argparse
import socketserver
import os.path as osp

parser = argparse.ArgumentParser(
    description='Simple lightweight TCP file server')
parser.add_argument('--port',
                    default=10000,
                    help="TCP port to be listened")


class TCPHandler(socketserver.StreamRequestHandler):
    timeout = 5

    def handle(self):
        req = self.request.recv(2048)
        print(req)
        if req == b'FILE_LIST':
            self.list_files()
        elif str(req, "UTF-8").startswith("DOWNLOAD"):
            self.send_file(str(req, "UTF-8").split(" ")[1])

    def send_file(self, file):
        print(file)
        print("Sending file....")
        with open('files/%s' % file, 'rb') as fp:
            buf = fp.read(1024)
            while buf:
                self.request.sendall(buf)
                buf = fp.read(1024)
        ack = self.request.recv(2048)
        assert ack == b'OK'
        print("file sent successful")

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


class ThreadedTCPServer(socketserver.ForkingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        socketserver.TCPServer.__init__(self, server_address,
                                        RequestHandlerClass)


if __name__ == '__main__':
    args = parser.parse_args()
    HOST, PORT = '0.0.0.0', int(args.port)
    server = ThreadedTCPServer((HOST, PORT), TCPHandler)
    print("Now listening on %s:%d" % (HOST, PORT))
    print("Press Ctrl+C to Stop")
    while True:
        try:
            server.handle_request()
        except KeyboardInterrupt:
            server.server_close()
            break

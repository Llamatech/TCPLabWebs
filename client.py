#! /usr/bin/env python3

from __future__ import unicode_literals

import os
import sys
import time
import math
import socket
import humanize
import argparse
import subprocess
import os.path as osp
from qtpy.QtCore import QMutex, QMutexLocker, Qt, QThread, Signal, Slot
from qtpy.QtWidgets import (QHBoxLayout, QLabel,
                            QTreeWidgetItem, QVBoxLayout, QWidget,
                            QProgressBar, QTreeWidget, QApplication,
                            QToolButton)


parser = argparse.ArgumentParser(
    description='Simple lightweight TCP download client')
parser.add_argument('--port',
                    default=10000,
                    help="Server TCP port")
parser.add_argument('--host',
                    default='127.0.0.1',
                    help="Server hostname")


def open_file(filename):
    if sys.platform == "win32":
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])


def create_toolbutton(parent, text=None, shortcut=None, icon=None, tip=None,
                      toggled=None, triggered=None,
                      autoraise=True, text_beside_icon=False):
    """Create a QToolButton"""
    button = QToolButton(parent)
    if text is not None:
        button.setText(text)
    if text is not None or tip is not None:
        button.setToolTip(text if tip is None else tip)
    if text_beside_icon:
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    button.setAutoRaise(autoraise)
    if triggered is not None:
        button.clicked.connect(triggered)
    if toggled is not None:
        button.toggled.connect(toggled)
        button.setCheckable(True)
    if shortcut is not None:
        button.setShortcut(shortcut)
    return button


class ListLocalFilesThread(QThread):
    sig_finished = Signal()
    sig_file_recv = Signal(str, int)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.mutex = QMutex()
        self.stopped = None

    def initialize(self, folder):
        self.folder = folder

    def run(self):
        for path, dirs, files in os.walk(self.folder):
            for file in files:
                file_path = osp.join(path, file)
                size = os.stat(file_path).st_size
                self.sig_file_recv.emit(file, size)
        self.sig_finished.emit()


class RecoverFilesThread(QThread):
    """Find in files search thread"""
    sig_finished = Signal()
    sig_file_recv = Signal(str, int)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.mutex = QMutex()
        self.stopped = None

    def initialize(self, host, port):
        self.host = host
        self.port = port

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.send(b"FILE_LIST")
        self.recv_files()
        self.stop()
        self.sig_finished.emit()

    def stop(self):
        with QMutexLocker(self.mutex):
            self.stopped = True
            self.sock.close()

    def recv_files(self):
        info = str(self.sock.recv(1024), "utf-8")
        while info != 'END':
            with QMutexLocker(self.mutex):
                if self.stopped:
                    return False
            print(info)
            print(info.split(','))
            file, size = info.split(',')
            size = int(size)
            self.sig_file_recv.emit(file, size)
            self.sock.send(b'OK')
            info = str(self.sock.recv(1024), "UTF-8")


class DownloadFileThread(QThread):
    sig_finished = Signal()
    sig_current_chunk = Signal(int, int)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.mutex = QMutex()
        self.stopped = None
        self.canceled = False

    def initialize(self, host, port, file, size):
        self.host = host
        self.port = port
        self.file = osp.join('downloads', file)
        self.msglen = size

    def run(self):
        self.start_time = time.time()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bufsize = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        bufsize *= 1
        print(bufsize)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF,
                             int(bufsize))
        self.sock.connect((self.host, self.port))
        s = "DOWNLOAD %s" % (self.file.split("/")[1])
        self.sock.send(str.encode(s))
        self.download_file()
        self.stop()
        self.sig_finished.emit()

    def stop(self):
        with QMutexLocker(self.mutex):
            self.stopped = True
            self.canceled = True
            self.sock.close()
            print("Time elapsed: {0}".format(time.time() - self.start_time))

    def download_file(self):
        # chunks = []
        num_chunks = 0
        bytes_recd = 0

        with open(self.file, 'wb') as fp:
            while bytes_recd < self.msglen:
                with QMutexLocker(self.mutex):
                    if self.stopped:
                        return False
                chunk_size = int(1024 * 1)
                chunk = self.sock.recv(min(self.msglen - bytes_recd,
                                       chunk_size))
                if chunk == b'':
                    raise RuntimeError("socket connection broken")
                # chunks.append(chunk)
                fp.write(chunk)
                bytes_recd = bytes_recd + len(chunk)
                num_chunks += 1
                self.sig_current_chunk.emit(num_chunks, bytes_recd)
                print('chunk # %d' % num_chunks)
                print('Size of chunk: %f' % len(chunk))
                print('Bytes received until now: %f' % bytes_recd)
        self.sock.send(b'OK')


class FileProgressBar(QWidget):
    """Simple progress bar with a label"""
    MAX_LABEL_LENGTH = 60

    def __init__(self, parent, *args, **kwargs):
        QWidget.__init__(self, parent)
        self.pap = parent
        self.status_text = QLabel(self)
        self.bar = QProgressBar(self)
        self.bar.setRange(0, 0)
        layout = QVBoxLayout()
        layout.addWidget(self.status_text)
        layout.addWidget(self.bar)
        self.setLayout(layout)

    def __truncate(self, text):
        ellipsis = '...'
        part_len = (self.MAX_LABEL_LENGTH - len(ellipsis)) / 2.0
        left_text = text[:int(math.ceil(part_len))]
        right_text = text[-int(math.floor(part_len)):]
        return left_text + ellipsis + right_text

    @Slot(str, int)
    def set_label_file(self, file, size):
        text = self.__truncate(file)
        status_str = 'Downloading file list: {0} ({1})'.format(
            text, humanize.naturalsize(size))
        self.status_text.setText(status_str)

    def set_bounds(self, a, b):
        self.bar.setRange(a, b)

    def reset_files(self):
        self.status_text.setText("  Downloading file(s)...")
        self.bar.show()

    def reset_status(self):
        self.status_text.setText("  Download Complete!")
        self.bar.hide()

    @Slot(str, int, int, int)
    def update_progress(self, file, num_chunks, bytes_recv, total_bytes):
        text = "  Downloading {0} - {1}/{2} (Chunk {3})"
        self.status_text.setText(text.format(
            file, humanize.naturalsize(bytes_recv),
            humanize.naturalsize(total_bytes), num_chunks))
        self.bar.setValue(bytes_recv)


class DownloadButtons(QWidget):
    start_sig = Signal()
    stop_sig = Signal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.start = create_toolbutton(self, text="Download",
                                       triggered=lambda: self.start_sig.emit(),
                                       tip="Start Download")
        self.stop = create_toolbutton(self, text="Stop",
                                      triggered=lambda: self.stop_sig.emit(),
                                      tip="Stop Download")
        self.stop.setEnabled(False)
        self.start.setEnabled(False)
        layout = QHBoxLayout()
        layout.addWidget(self.start)
        layout.addWidget(self.stop)
        self.setLayout(layout)


class FileListWidget(QTreeWidget):
    file_selected_sig = Signal(str, int)

    def __init__(self, parent):
        QTreeWidget.__init__(self, parent)
        self.setItemsExpandable(True)
        self.setColumnCount(1)
        self.data = {}
        self.itemActivated.connect(self.activated)
        self.itemClicked.connect(self.clicked)
        self.itemSelectionChanged.connect(self.item_selection_changed)
        self.item_selection_changed()
        self.itemSelectionChanged.connect(self.item_selection_changed)
        self.item_selection_changed()

    def set_title(self, title):
        self.setHeaderLabels([title])

    def activated(self, item):
        """Double click event."""
        itemdata = self.data.get(id(self.currentItem()))
        if itemdata is not None:
            self.file_selected_sig.emit(*itemdata)

    def clicked(self, item):
        """Single click event."""
        self.activated(item)

    def item_selection_changed(self):
        """Item selection has changed"""
        pass

    @Slot(str, int)
    def add_file(self, file, size):
        file_item = QTreeWidgetItem(self, [file + ' - ' +
                                           humanize.naturalsize(size)],
                                    QTreeWidgetItem.Type)
        self.data[id(file_item)] = (file, size)


class FileDownloaderWidget(QWidget):

    def __init__(self, parent, host='127.0.0.1', port=12000):
        QWidget.__init__(self, parent)
        self.thread = None
        self.host = host
        self.port = port
        self.selected_file = None
        self.size = 0
        self.files = FileListWidget(self)
        self.local_files = FileListWidget(self)
        self.download_buttons = DownloadButtons(self)
        self.progress_bar = FileProgressBar(self)
        self.progress_bar.hide()
        self.files.set_title("Server files")
        self.local_files.set_title("Local files")
        layout = QVBoxLayout()
        layout.addWidget(self.files)
        layout.addWidget(self.local_files)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.download_buttons)
        self.setLayout(layout)

        self.download_buttons.start_sig.connect(self.start_download)
        self.download_buttons.stop_sig.connect(self.stop_and_reset_thread)
        self.files.file_selected_sig.connect(self.set_selected_file)
        self.local_files.file_selected_sig.connect(self.open_selected_file)

    def get_file_list(self):
        self.stop_and_reset_thread()
        self.thread = RecoverFilesThread(self)
        self.thread.initialize(self.host, self.port)
        self.thread.sig_finished.connect(self.download_complete)
        self.thread.sig_file_recv.connect(self.files.add_file)
        self.thread.sig_file_recv.connect(self.progress_bar.set_label_file)
        self.progress_bar.reset_files()
        self.thread.start()
        self.download_buttons.stop.setEnabled(True)
        self.download_buttons.start.setEnabled(False)
        self.progress_bar.show()

    @Slot(str, int)
    def set_selected_file(self, file, size):
        self.selected_file = file
        self.size = size
        print((file, size))
        self.progress_bar.set_bounds(0, size)

    @Slot(str, int)
    def open_selected_file(self, file, size):
        file_path = osp.abspath(osp.join('downloads', file))
        open_file(file_path)

    def start_download(self):
        if self.selected_file is not None:
            self.stop_and_reset_thread()
            self.thread = DownloadFileThread(self)
            self.thread.initialize(self.host, self.port,
                                   self.selected_file, self.size)
            self.thread.sig_finished.connect(self.download_complete)
            self.thread.sig_current_chunk.connect(
                lambda x, y:
                self.progress_bar.update_progress(self.selected_file, x,
                                                  y, self.size))
            self.progress_bar.reset_files()
            self.thread.start()
            self.download_buttons.stop.setEnabled(True)
            self.download_buttons.start.setEnabled(False)

    def download_complete(self):
        self.progress_bar.reset_status()
        self.download_buttons.stop.setEnabled(False)
        self.download_buttons.start.setEnabled(True)
        self.list_local_files()

    def list_local_files(self):
        self.local_files.clear()
        self.local_file_thread = ListLocalFilesThread(self)
        self.local_file_thread.initialize('downloads')
        self.local_file_thread.sig_file_recv.connect(self.local_files.add_file)
        self.local_file_thread.sig_finished.connect(self.reset_local_thread)
        self.local_file_thread.start()

    def reset_local_thread(self):
        if self.local_file_thread.isRunning():
            self.local_file_thread.wait()
        self.local_file_thread.setParent(None)
        self.local_file_thread = None

    def stop_and_reset_thread(self):
        if self.thread is not None:
            if self.thread.isRunning():
                self.thread.sig_finished.disconnect(self.download_complete)
                self.thread.stop()
                self.thread.wait()
            self.thread.setParent(None)
            self.thread = None
            self.download_complete()


if __name__ == '__main__':
    args = parser.parse_args()
    host = args.host
    port = int(args.port)
    app = QApplication.instance()
    if app is None:
        app = QApplication(['Client'])
    widget = FileDownloaderWidget(None, host=host, port=port)
    widget.resize(640, 480)
    widget.show()
    widget.get_file_list()
    sys.exit(app.exec_())

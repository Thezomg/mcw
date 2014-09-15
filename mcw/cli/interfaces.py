import asyncio
import clize
import json
import os
import random
import string
import codecs

class ServerWrapper(object):
    """
    ServerWrapper starts the server process and handles the standard in and out.
    """

    def __init__(self, socket_path=None):
        self.process = None
        self.controller = None
        self.events = asyncio.Queue(loop=asyncio.get_event_loop())
        self.socket_path = socket_path
        self._event_process = None

    @asyncio.coroutine
    def start_server(self):
        if self.socket_path is not None:
            print("Socket path provided")
            try:
                try:
                    os.unlink(self.socket_path)
                except:
                    print("File doesn't exist")
                #self.server = self._create_socket(self.socket_path)
                #yield from asyncio.start_unix_server(CommandServer.factory(self), self.socket_path)
                yield from self._create_socket(self.socket_path)
                return
            except:
                raise Exception('Failed to create control socket')
        for i in range(16):
            print(i)
            try:
                yield from self._create_socket('/tmp/mcw-{}.sock'.format(''.join(
                    random.choice(string.ascii_lowercase) for i in range(16))))
                return
            except:
                print("ERROR!")
                continue

        raise Exception('Failed to create control socket')

    @asyncio.coroutine
    def _create_socket(self, path):
        if os.path.exists(path):
            raise FileExistsError('The socket already exists')
        print("Creating socket")
        server = yield from asyncio.start_unix_server(CommandServer.factory(self), path)
        print('Socket path: {}'.format(path))
        return server

    @asyncio.coroutine
    def start_process(self, command):
        loop = asyncio.get_event_loop()
        factory = ProcessProtocol.factory(self)
        transport, self.process = yield from loop.subprocess_exec(
                factory, *command)
        return transport.get_pid()

    def run(self):
        asyncio.async(self.start_server())
        asyncio.get_event_loop().run_forever()

    @asyncio.coroutine
    def new_connection(self, sock):
        if self.controller is not None:
            self.controller.close()
        self.controller = sock
        self._event_process = asyncio.async(self.process_events())

    def connection_closed(self):
        if self._event_process is not None:
            self._event_process.cancel()
        self.controller = None

    @asyncio.coroutine
    def send_event(self, **kwargs):
        yield from self.events.put(kwargs)

    @asyncio.coroutine
    def process_events(self):
        while not self._event_process.done():
            ev = yield from self.events.get()
            try:
                if self.controller is not None:
                    yield from self.controller.definitely_write(ev)
            except:
                print('Failed to write to socket')

    def process_exited(self):
        self.process = None

    def handle_event(self, obj):
        typ = obj['type']
        if typ == 'start':
            if self.process is None:
                pid = yield from self.start_process(obj['command'])
                yield from self.send_event(type='start', result='success', pid=pid)
            else:
                yield from self.send_event(type='error', message='fuck off')
        elif typ == 'write':
            yield from self.process.ev_write(obj)
        elif typ == 'kill':
            yield from self.process.ev_kill(obj)

class StdStream:
    def __init__(self, encoding, errors='replace'):
        self.buffer_ = ''
        self.decoder = codecs.getincrementaldecoder(encoding)(errors)

    def feed_data(self, data):
        self.buffer_ += self.decoder.decode(data)

    def get_lines(self):
        *lines, self.buffer_ = self.buffer_.split('\n')
        return lines

class ProcessProtocol(asyncio.SubprocessProtocol):
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self.stdout = StdStream('utf8')
        self.stderr = StdStream('utf8')

    @classmethod
    def factory(cls, wrapper):
        def factory():
            return cls(wrapper)
        return factory

    def connection_made(self, transport):
        self.process = transport

    def ev_write(self, data):
        self.process.write(data['data'].encode(encoding))

    def ev_kill(self, data):
        self.process.send_signal(data['signal'])

    def pipe_data_received(self, fd, data):
        if fd == 1:
            typ = 'stdout'
            stream = self.stdout
        else:
            typ = 'stderr'
            stream = self.stderr
        stream.feed_data(data)
        for line in stream.get_lines():
            asyncio.async(self.wrapper.send_event(type=typ, data=line))

    def process_exited(self):
        self.wrapper.process_exited()
        asyncio.async(self.wrapper.send_event(type="exit", status=self.process.get_returncode()))

class CommandServer(asyncio.Protocol):
    def __init__(self, wrapper, reader, writer):
        self.wrapper = wrapper
        self.reader = reader
        self.writer = writer

    def close(self):
        self.writer.close()

    @classmethod
    def factory(cls, wrapper):
        @asyncio.coroutine
        def callback(reader, writer):
            self = cls(wrapper, reader, writer)
            yield from wrapper.new_connection(self)
            yield from self.run()
        return callback

    @asyncio.coroutine
    def run(self):
        while True:
            line = yield from self.reader.readline()
            if line == b'' or not line.endswith(b"\n"):
                self.wrapper.connection_closed()
                return
            line = line.decode('utf8')
            yield from self.wrapper.handle_event(json.loads(line))

    @asyncio.coroutine
    def definitely_write(self, data):
        self.writer.write((json.dumps(data) + '\n').encode('utf8'))
        yield from self.writer.drain()

@clize.clize
def start(*, socket_path=None, debug=False):
    import logging
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        asyncio.get_event_loop().set_debug(True)
    else:
        logging.basicConfig(level=logging.INFO)

    sw = ServerWrapper(socket_path=socket_path)
    sw.run()

@clize.clize
def attach(server_name):
    print('Connect to {}'.format(server_name))

def main():
    clize.run(attach, start)

if __name__ == '__main__':
    clize.run(_run)

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

    def __init__(self, plugin_path=None):
        self.server_process = None
        self.plugin_process = None
        self._to_plugin = asyncio.Queue(loop=asyncio.get_event_loop())
        self.plugin_path = None
        self._plugin_write = None

    @asyncio.coroutine
    def start_server_process(self, command):
        loop = asyncio.get_event_loop()
        factory = ProcessProtocol.factory(self)
        transport, self.server_process = yield from loop.subprocess_exec(
                factory, *command)
        return transport.get_pid()

    @asyncio.coroutine
    def start_plugin_process(self):
        loop = asyncio.get_event_loop()
        factory = ProcessProtocol.factory(self)
        transport, self.plugin_service = yield from loop.subprocess_exec(
                factory, 'mcw', 'plugin')
        self._plugin_write = asyncio.async(self.write_to_plugin())
        return transport.get_pid()

    def run(self):
        asyncio.async(self.start_plugin_process())
        asyncio.get_event_loop().run_forever()

    def connection_closed(self):
        if self._event_process is not None:
            self._event_process.cancel()
        self.controller = None

    @asyncio.coroutine
    def send_event(self, **kwargs):
        yield from self._to_plugin.put(kwargs)

    @asyncio.coroutine
    def write_to_plugin(self):
        while not self._plugin_write.done():
            ev = yield from self._to_plugin.get()
            try:
                yield from self.plugin.ev_write(ev + "\n")
            except:
                print('Failed to write to plugin process')

    def process_output(self, process, typ, data):
        if self.server_process == process:
            asyncio.async(self.send_event(type=typ, data=data))
        else:
            asyncio.async(self.handle_event(json.loads(data)))

    def process_exited(self, process, return_code):
        if self.server_process == process:
            self.server_process = None
            asyncio.async(self.send_event(type="exit", status=return_code))
        else:
            self.plugin_process = None
            self._plugin_write.cancel()

    @asyncio.coroutine
    def handle_event(self, obj):
        typ = obj['type']
        if typ == 'start':
            if self.server_process is None:
                pid = yield from self.start_server_process(obj['command'])
                yield from self.send_event(type='start', result='success', pid=pid)
            else:
                yield from self.send_event(type='error', message='Server is already running')
        elif typ == 'write':
            if self.server_process is not None:
                yield from self.server_process.ev_write(obj)
            else:
                yield from self.send_event(type='error', message='Server is not running')
        elif typ == 'kill':
            if self.server_process is not None:
                yield from self.server_process.ev_kill(obj)
            else:
                yield from self.send_event(type='error', message='Server is not running')
        elif typ == 'stdout':
            print("Got a stdout: {}".format(obj['message']))

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
            self.wrapper.process_output(self, typ, line)

    def process_exited(self):
        self.wrapper.process_exited(self, self.process.get_returncode())

@clize.clize
def start(*, socket_path=None, debug=False):
    import logging
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        asyncio.get_event_loop().set_debug(True)
    else:
        logging.basicConfig(level=logging.INFO)

    sw = ServerWrapper()
    sw.run()

@clize.clize
def attach(server_name):
    print('Connect to {}'.format(server_name))

@clize.clize
def plugin():
    print(json.dumps({"type": "stdout", "message": "received"}))

def main():
    clize.run(attach, start, plugin)

if __name__ == '__main__':
    main()

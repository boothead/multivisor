import collections
import errno
from eventlet import wsgi
from eventlet import pools
import eventlet
from eventlet.common import get_errno
from eventlet.green import socket
from webob import Response
from webob.exc import HTTPException
from pprint import pformat

from multivisor.interfaces import IWebsocketUpgradeRequest


class IncorrectlyConfigured(Exception):
    """Exception to use in place of an assertion error"""

class WebSocketView(object):
    """A view for handling websockets

    This view handles both the upgrade request and the ongoing socket
    communiction.
    """

    def __init__(self, request):
        self.request = request
        self.environ = request.environ
        self.sock = self.environ['eventlet.input'].get_socket()

    def __call__(self):
        import ipdb;ipdb.set_trace()
        if IWebsocketUpgradeRequest.providedBy(self.request):
            return self.handle_upgrade()
        raise IncorrectlyConfigured("IWebsocketUpgradeRequest is not provided by "
                                    "this request. Make sure the correct INewRequest "
                                    "adapter is hooked up")

    def verify_client(self):
        pass

    def handler(self, ws):
        raise NotImplementedError

    def handle_websocket(self, ws):
        ws = WebSocket(self.sock, self.environ)

        try:
            self.handler(ws)
        except socket.error, e:
            if get_errno(e) != errno.EPIPE:
                raise
        # use this undocumented feature of eventlet.wsgi to close the connection properly
        resp = Response()
        resp.app_iter = wsgi.ALREADY_HANDLED
        return resp

    def handle_upgrade(self):
        if not (self.environ['HTTP_CONNECTION'] == 'Upgrade' and
                self.environ['HTTP_UPGRADE'] == 'WebSocket'):
            return HTTPException('Bad:\n%s' % pformat(self.environ), headerlist=[('Connection','close')])
        sock = self.environ['eventlet.input'].get_socket()
        handshake_reply = ("HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
                           "Upgrade: WebSocket\r\n"
                           "Connection: Upgrade\r\n"
                           "WebSocket-Origin: %s\r\n"
                           "WebSocket-Location: ws://%s%s\r\n\r\n" % (
                                self.request.host_url,
                                self.request.host, self.request.path_info))
        sock.sendall(handshake_reply)
        ws = WebSocket(self.sock, self.environ)
        return self.handle_websocket(ws)

class WebSocket(object):
    """Handles access to the actual socket"""

    def __init__(self, sock, environ):
        """
        :param socket: The eventlet socket
        :type socket: :class:`eventlet.greenio.GreenSocket`
        :param environ: The wsgi environment
        """
        self.socket = sock
        self.origin = environ.get('HTTP_ORIGIN')
        self.protocol = environ.get('HTTP_WEBSOCKET_PROTOCOL')
        self.path = environ.get('PATH_INFO')
        self.environ = environ
        self._buf = ""
        self._msgs = collections.deque()
        self._sendlock = pools.TokenPool(1)

    @staticmethod
    def pack_message(message):
        """Pack the message inside ``00`` and ``FF``

        As per the dataframing section (5.3) for the websocket spec
        """
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        elif not isinstance(message, str):
            message = str(message)
        packed = "\x00%s\xFF" % message
        return packed

    def parse_messages(self):
        """ Parses for messages in the buffer *buf*.  It is assumed that
        the buffer contains the start character for a message, but that it
        may contain only part of the rest of the message. NOTE: only understands
        lengthless messages for now.

        Returns an array of messages, and the buffer remainder that didn't contain
        any full messages."""
        msgs = []
        end_idx = 0
        buf = self._buf
        while buf:
            assert ord(buf[0]) == 0, "Don't understand how to parse this type of message: %r" % buf
            end_idx = buf.find("\xFF")
            if end_idx == -1:
                break
            msgs.append(buf[1:end_idx].decode('utf-8', 'replace'))
            buf = buf[end_idx+1:]
        self._buf = buf
        return msgs
    
    def send(self, message):
        """Send a message to the client"""
        packed = self.pack_message(message)
        # if two greenthreads are trying to send at the same time
        # on the same socket, sendlock prevents interleaving and corruption
        t = self._sendlock.get()
        try:
            self.socket.sendall(packed)
        finally:
            self._sendlock.put(t)
            
    def wait(self):
        """Waits for an deserializes messages"""

        while not self._msgs:
            # no parsed messages, must mean buf needs more data
            delta = self.socket.recv(1024)
            if delta == '':
                return None
            self._buf += delta
            msgs = self.parse_messages()
            self._msgs.extend(msgs)
        return self._msgs.popleft()

    def close(self):
        self.socket.shutdown(True)


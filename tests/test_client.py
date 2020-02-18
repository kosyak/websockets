import email.utils
import unittest
import unittest.mock

from websockets.client import *
from websockets.connection import CONNECTING, OPEN
from websockets.datastructures import Headers
from websockets.events import Accept, Connect, Reject
from websockets.exceptions import InvalidHandshake, InvalidHeader, NegotiationError
from websockets.http import USER_AGENT
from websockets.http11 import Request, Response
from websockets.utils import accept

from .test_utils import ACCEPT, KEY


DATE = email.utils.formatdate(usegmt=True)


class OpExtension:
    name = "x-op"

    def __init__(self, op=None):
        self.op = op

    def decode(self, frame, *, max_size=None):
        return frame

    def encode(self, frame):
        return frame

    def __eq__(self, other):
        return isinstance(other, OpExtension) and self.op == other.op


class ClientOpExtensionFactory:
    name = "x-op"

    def __init__(self, op=None):
        self.op = op

    def get_request_params(self):
        return [("op", self.op)]

    def process_response_params(self, params, accepted_extensions):
        if params != [("op", self.op)]:
            raise NegotiationError()
        return OpExtension(self.op)


class Rsv2Extension:
    name = "x-rsv2"

    def decode(self, frame, *, max_size=None):
        assert frame.rsv2
        return frame._replace(rsv2=False)

    def encode(self, frame):
        assert not frame.rsv2
        return frame._replace(rsv2=True)

    def __eq__(self, other):
        return isinstance(other, Rsv2Extension)


class ClientRsv2ExtensionFactory:
    name = "x-rsv2"

    def get_request_params(self):
        return []

    def process_response_params(self, params, accepted_extensions):
        return Rsv2Extension()


class ConnectTests(unittest.TestCase):
    def test_send_connect(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("wss://example.com/test")
        connect = client.connect()
        self.assertIsInstance(connect, Connect)
        bytes_to_send = client.send(connect)
        self.assertEqual(
            bytes_to_send,
            (
                f"GET /test HTTP/1.1\r\n"
                f"Host: example.com\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {KEY}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"User-Agent: {USER_AGENT}\r\n"
                f"\r\n"
            ).encode(),
        )

    def test_connect_request(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("wss://example.com/test")
        connect = client.connect()
        self.assertIsInstance(connect.request, Request)
        self.assertEqual(connect.request.path, "/test")
        self.assertEqual(
            connect.request.headers,
            Headers(
                {
                    "Host": "example.com",
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                    "Sec-WebSocket-Version": "13",
                    "User-Agent": USER_AGENT,
                }
            ),
        )

    def test_path(self):
        client = ClientConnection("wss://example.com/endpoint?test=1")
        request = client.connect().request

        self.assertEqual(request.path, "/endpoint?test=1")

    def test_port(self):
        for uri, host in [
            ("ws://example.com/", "example.com"),
            ("ws://example.com:80/", "example.com"),
            ("ws://example.com:8080/", "example.com:8080"),
            ("wss://example.com/", "example.com"),
            ("wss://example.com:443/", "example.com"),
            ("wss://example.com:8443/", "example.com:8443"),
        ]:
            with self.subTest(uri=uri):
                client = ClientConnection(uri)
                request = client.connect().request

                self.assertEqual(request.headers["Host"], host)

    def test_user_info(self):
        client = ClientConnection("wss://hello:iloveyou@example.com/")
        request = client.connect().request

        self.assertEqual(request.headers["Authorization"], "Basic aGVsbG86aWxvdmV5b3U=")

    def test_origin(self):
        client = ClientConnection("wss://example.com/", origin="https://example.com")
        request = client.connect().request

        self.assertEqual(request.headers["Origin"], "https://example.com")

    def test_extensions(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory()]
        )
        request = client.connect().request

        self.assertEqual(request.headers["Sec-WebSocket-Extensions"], "x-op; op")

    def test_subprotocols(self):
        client = ClientConnection("wss://example.com/", subprotocols=["chat"])
        request = client.connect().request

        self.assertEqual(request.headers["Sec-WebSocket-Protocol"], "chat")

    def test_extra_headers(self):
        for extra_headers in [
            Headers({"X-Spam": "Eggs"}),
            {"X-Spam": "Eggs"},
            [("X-Spam", "Eggs")],
        ]:
            with self.subTest(extra_headers=extra_headers):
                client = ClientConnection(
                    "wss://example.com/", extra_headers=extra_headers
                )
                request = client.connect().request

                self.assertEqual(request.headers["X-Spam"], "Eggs")

    def test_extra_headers_overrides_user_agent(self):
        client = ClientConnection(
            "wss://example.com/", extra_headers={"User-Agent": "Other"}
        )
        request = client.connect().request

        self.assertEqual(request.headers["User-Agent"], "Other")


class CheckResponseTests(unittest.TestCase):
    def test_receive_accept(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [accept], bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 101 Switching Protocols\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {ACCEPT}\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"\r\n"
            ).encode(),
        )
        self.assertIsInstance(accept, Accept)
        self.assertEqual(bytes_to_send, b"")
        self.assertEqual(client.state, OPEN)

    def test_receive_reject(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [reject], bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 404 Not Found\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"Content-Length: 12\r\n"
                f"Content-Type: text/plain\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"Sorry folks."
            ).encode(),
        )
        self.assertIsInstance(reject, Reject)
        self.assertEqual(bytes_to_send, b"")
        self.assertEqual(client.state, CONNECTING)

    def test_accept_response(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [accept], _bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 101 Switching Protocols\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {ACCEPT}\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"\r\n"
            ).encode(),
        )
        self.assertEqual(accept.response.status_code, 101)
        self.assertEqual(accept.response.reason_phrase, "Switching Protocols")
        self.assertEqual(
            accept.response.headers,
            Headers(
                {
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Accept": "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
                    "Date": DATE,
                    "Server": USER_AGENT,
                }
            ),
        )
        self.assertIsNone(accept.response.body)

    def test_reject_response(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [reject], _bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 404 Not Found\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"Content-Length: 12\r\n"
                f"Content-Type: text/plain\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"Sorry folks."
            ).encode(),
        )
        self.assertEqual(reject.response.status_code, 404)
        self.assertEqual(reject.response.reason_phrase, "Not Found")
        self.assertEqual(
            reject.response.headers,
            Headers(
                {
                    "Date": DATE,
                    "Server": USER_AGENT,
                    "Content-Length": "12",
                    "Content-Type": "text/plain",
                    "Connection": "close",
                }
            ),
        )
        # Currently websockets doesn't read response bodies.
        self.assertIsNone(reject.response.body)

    def make_accept_response(self, client):
        request = client.connect().request
        return Response(
            status_code=101,
            reason_phrase="Switching Protocols",
            headers=Headers(
                {
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Accept": accept(
                        request.headers["Sec-WebSocket-Key"]
                    ),
                }
            ),
        )

    def test_basic(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)

        client.process_response(response)  # does not raise an exception

    def test_missing_connection(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Connection"]

        with self.assertRaises(InvalidHeader, msg="missing Connection header"):
            client.process_response(response)

    def test_invalid_connection(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Connection"]
        response.headers["Connection"] = "Close"

        with self.assertRaises(InvalidHeader, msg="invalid Connection header: Close"):
            client.process_response(response)

    def test_missing_upgrade(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Upgrade"]

        with self.assertRaises(InvalidHeader, msg="missing Upgrade header"):
            client.process_response(response)

    def test_invalid_upgrade(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Upgrade"]
        response.headers["Upgrade"] = "h2c"

        with self.assertRaises(InvalidHeader, msg="invalid Upgrade header: h2c"):
            client.process_response(response)

    def test_missing_accept(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Sec-WebSocket-Accept"]

        with self.assertRaises(
            InvalidHeader, msg="missing Sec-WebSocket-Accept header"
        ):
            client.process_response(response)

    def test_multiple_accept(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Accept"] = ACCEPT

        with self.assertRaises(
            InvalidHeader, msg="more than one Sec-WebSocket-Accept header found"
        ):
            client.process_response(response)

    def test_invalid_accept(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Sec-WebSocket-Accept"]
        response.headers["Sec-WebSocket-Accept"] = ACCEPT

        with self.assertRaises(
            InvalidHeader, msg=f"invalid Sec-WebSocket-Accept header: {ACCEPT}"
        ):
            client.process_response(response)

    def test_no_extensions(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)

        client.process_response(response)
        self.assertEqual(client.extensions, [])

    def test_extension(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory()]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op"

        client.process_response(response)
        self.assertEqual(client.extensions, [OpExtension()])

    def test_unexpected_extension(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op"

        with self.assertRaises(InvalidHandshake, msg="no extensions supported"):
            client.process_response(response)

    def test_supported_extension(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientRsv2ExtensionFactory()]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-rsv2"

        client.process_response(response)
        self.assertEqual(client.extensions, [Rsv2Extension()])

    def test_unsupported_extension(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientRsv2ExtensionFactory()]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op"

        with self.assertRaises(
            InvalidHandshake,
            msg="Unsupported extension: name = x-op, params = [('op', None)]",
        ):
            client.process_response(response)

    def test_supported_extension_parameters(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory("this")]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op=this"

        client.process_response(response)
        self.assertEqual(client.extensions, [OpExtension("this")])

    def test_unsupported_extension_parameters(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory("this")]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op=that"

        with self.assertRaises(
            InvalidHandshake,
            msg="Unsupported extension: name = x-op, params = [('op', 'that')]",
        ):
            client.process_response(response)

    def test_multiple_supported_extension_parameters(self):
        client = ClientConnection(
            "wss://example.com/",
            extensions=[
                ClientOpExtensionFactory("this"),
                ClientOpExtensionFactory("that"),
            ],
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op=that"

        client.process_response(response)
        self.assertEqual(client.extensions, [OpExtension("that")])

    def test_multiple_extensions(self):
        client = ClientConnection(
            "wss://example.com/",
            extensions=[ClientOpExtensionFactory(), ClientRsv2ExtensionFactory()],
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op"
        response.headers["Sec-WebSocket-Extensions"] = "x-rsv2"

        client.process_response(response)
        self.assertEqual(client.extensions, [OpExtension(), Rsv2Extension()])

    def test_multiple_extensions_order(self):
        client = ClientConnection(
            "wss://example.com/",
            extensions=[ClientOpExtensionFactory(), ClientRsv2ExtensionFactory()],
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-rsv2"
        response.headers["Sec-WebSocket-Extensions"] = "x-op;op"

        client.process_response(response)
        self.assertEqual(client.extensions, [Rsv2Extension(), OpExtension()])

    def test_no_subprotocol(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)

        client.process_response(response)
        self.assertIsNone(client.subprotocol)

    def test_subprotocol(self):
        client = ClientConnection("wss://example.com/", subprotocols=["chat"])
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "chat"

        client.process_response(response)
        self.assertEqual(client.subprotocol, "chat")

    def test_unexpected_subprotocol(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "chat"

        with self.assertRaises(InvalidHandshake, msg="no subprotocols supported"):
            client.process_response(response)

    def test_multiple_subprotocols(self):
        client = ClientConnection(
            "wss://example.com/", subprotocols=["superchat", "chat"]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "superchat"
        response.headers["Sec-WebSocket-Protocol"] = "chat"

        with self.assertRaises(
            InvalidHandshake, msg="multiple subprotocols: superchat, chat"
        ):
            client.process_response(response)

    def test_supported_subprotocol(self):
        client = ClientConnection(
            "wss://example.com/", subprotocols=["superchat", "chat"]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "chat"

        client.process_response(response)
        self.assertEqual(client.subprotocol, "chat")

    def test_unsupported_subprotocol(self):
        client = ClientConnection(
            "wss://example.com/", subprotocols=["superchat", "chat"]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "otherchat"

        with self.assertRaises(
            InvalidHandshake, msg="unsupported subprotocol: otherchat"
        ):
            client.process_response(response)

from websockets.datastructures import Headers
from websockets.exceptions import SecurityError
from websockets.http11 import *
from websockets.http11 import parse_headers
from websockets.streams import StreamReader

from .utils import GeneratorTestCase


class RequestTests(GeneratorTestCase):
    def setUp(self):
        super().setUp()
        self.reader = StreamReader()

    def test_parse(self):
        # Example from the protocol overview in RFC 6455
        self.reader.feed_data(
            b"GET /chat HTTP/1.1\r\n"
            b"Host: server.example.com\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            b"Origin: http://example.com\r\n"
            b"Sec-WebSocket-Protocol: chat, superchat\r\n"
            b"Sec-WebSocket-Version: 13\r\n"
            b"\r\n"
        )
        request = self.assertGeneratorReturns(Request.parse(self.reader.readline))
        self.assertEqual(request.path, "/chat")
        self.assertEqual(request.headers["Upgrade"], "websocket")

    def test_parse_empty(self):
        self.reader.feed_eof()
        with self.assertRaisesRegex(
            EOFError, "connection closed while reading HTTP request line"
        ):
            next(Request.parse(self.reader.readline))

    def test_parse_invalid_request_line(self):
        self.reader.feed_data(b"GET /\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "invalid HTTP request line: GET /"):
            next(Request.parse(self.reader.readline))

    def test_parse_unsupported_method(self):
        self.reader.feed_data(b"OPTIONS * HTTP/1.1\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "unsupported HTTP method: OPTIONS"):
            next(Request.parse(self.reader.readline))

    def test_parse_unsupported_version(self):
        self.reader.feed_data(b"GET /chat HTTP/1.0\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "unsupported HTTP version: HTTP/1.0"):
            next(Request.parse(self.reader.readline))

    def test_parse_invalid_header(self):
        self.reader.feed_data(b"GET /chat HTTP/1.1\r\nOops\r\n")
        with self.assertRaisesRegex(ValueError, "invalid HTTP header line: Oops"):
            next(Request.parse(self.reader.readline))

    def test_serialize(self):
        # Example from the protocol overview in RFC 6455
        request = Request(
            "/chat",
            Headers(
                [
                    ("Host", "server.example.com"),
                    ("Upgrade", "websocket"),
                    ("Connection", "Upgrade"),
                    ("Sec-WebSocket-Key", "dGhlIHNhbXBsZSBub25jZQ=="),
                    ("Origin", "http://example.com"),
                    ("Sec-WebSocket-Protocol", "chat, superchat"),
                    ("Sec-WebSocket-Version", "13"),
                ]
            ),
        )
        self.assertEqual(
            request.serialize(),
            b"GET /chat HTTP/1.1\r\n"
            b"Host: server.example.com\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            b"Origin: http://example.com\r\n"
            b"Sec-WebSocket-Protocol: chat, superchat\r\n"
            b"Sec-WebSocket-Version: 13\r\n"
            b"\r\n",
        )


class ResponseTests(GeneratorTestCase):
    def setUp(self):
        super().setUp()
        self.reader = StreamReader()

    def test_parse(self):
        # Example from the protocol overview in RFC 6455
        self.reader.feed_data(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
            b"Sec-WebSocket-Protocol: chat\r\n"
            b"\r\n"
        )
        response = self.assertGeneratorReturns(Response.parse(self.reader.readline))
        self.assertEqual(response.status_code, 101)
        self.assertEqual(response.reason_phrase, "Switching Protocols")
        self.assertEqual(response.headers["Upgrade"], "websocket")

    def test_parse_empty(self):
        self.reader.feed_eof()
        with self.assertRaisesRegex(
            EOFError, "connection closed while reading HTTP status line"
        ):
            next(Response.parse(self.reader.readline))

    def test_parse_invalid_status_line(self):
        self.reader.feed_data(b"Hello!\r\n")
        with self.assertRaisesRegex(ValueError, "invalid HTTP status line: Hello!"):
            next(Response.parse(self.reader.readline))

    def test_parse_unsupported_version(self):
        self.reader.feed_data(b"HTTP/1.0 400 Bad Request\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "unsupported HTTP version: HTTP/1.0"):
            next(Response.parse(self.reader.readline))

    def test_parse_invalid_status(self):
        self.reader.feed_data(b"HTTP/1.1 OMG WTF\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "invalid HTTP status code: OMG"):
            next(Response.parse(self.reader.readline))

    def test_parse_unsupported_status(self):
        self.reader.feed_data(b"HTTP/1.1 007 My name is Bond\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "unsupported HTTP status code: 007"):
            next(Response.parse(self.reader.readline))

    def test_parse_invalid_reason(self):
        self.reader.feed_data(b"HTTP/1.1 200 \x7f\r\n\r\n")
        with self.assertRaisesRegex(ValueError, "invalid HTTP reason phrase: \\x7f"):
            next(Response.parse(self.reader.readline))

    def test_parse_invalid_header(self):
        self.reader.feed_data(b"HTTP/1.1 500 Internal Server Error\r\nOops\r\n")
        with self.assertRaisesRegex(ValueError, "invalid HTTP header line: Oops"):
            next(Response.parse(self.reader.readline))

    def test_serialize(self):
        # Example from the protocol overview in RFC 6455
        response = Response(
            101,
            "Switching Protocols",
            Headers(
                [
                    ("Upgrade", "websocket"),
                    ("Connection", "Upgrade"),
                    ("Sec-WebSocket-Accept", "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="),
                    ("Sec-WebSocket-Protocol", "chat"),
                ]
            ),
        )
        self.assertEqual(
            response.serialize(),
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n"
            b"Sec-WebSocket-Protocol: chat\r\n"
            b"\r\n",
        )

    def test_serialize_with_body(self):
        response = Response(
            200,
            "OK",
            Headers([("Content-Length", "13"), ("Content-Type", "text/plain")]),
            b"Hello world!\n",
        )
        self.assertEqual(
            response.serialize(),
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 13\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"Hello world!\n",
        )


class HeadersTests(GeneratorTestCase):
    def setUp(self):
        super().setUp()
        self.reader = StreamReader()

    def test_parse_invalid_name(self):
        self.reader.feed_data(b"foo bar: baz qux\r\n\r\n")
        with self.assertRaises(ValueError):
            next(parse_headers(self.reader.readline))

    def test_parse_invalid_value(self):
        self.reader.feed_data(b"foo: \x00\x00\x0f\r\n\r\n")
        with self.assertRaises(ValueError):
            next(parse_headers(self.reader.readline))

    def test_parse_too_long_value(self):
        self.reader.feed_data(b"foo: bar\r\n" * 257 + b"\r\n")
        with self.assertRaises(SecurityError):
            next(parse_headers(self.reader.readline))

    def test_parse_too_long_line(self):
        # Header line contains 5 + 4090 + 2 = 4097 bytes.
        self.reader.feed_data(b"foo: " + b"a" * 4090 + b"\r\n\r\n")
        with self.assertRaises(SecurityError):
            next(parse_headers(self.reader.readline))

    def test_parse_invalid_line_ending(self):
        self.reader.feed_data(b"foo: bar\n\n")
        with self.assertRaises(EOFError):
            next(parse_headers(self.reader.readline))

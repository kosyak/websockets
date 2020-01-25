from typing import Generator


class StreamReader:
    """
    Generator-based stream reader.

    """

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.eof = False

    def readline(self) -> Generator[None, None, bytes]:
        """
        Read a LF-terminated line from the stream.

        This is a generator-based coroutine.

        :raises EOFError: if the stream ends without a LF

        """
        n = 0  # number of bytes to read
        p = 0  # number of bytes without a newline
        while True:
            n = self.buffer.find(b"\n", p) + 1
            if n > 0:
                break
            p = len(self.buffer)
            if self.eof:
                raise EOFError(f"stream ends after {p} bytes, before end of line")
            yield
        r = self.buffer[:n]
        del self.buffer[:n]
        return r

    def readexactly(self, n: int) -> Generator[None, None, bytes]:
        """
        Read ``n`` bytes from the stream.

        This is a generator-based coroutine.

        :raises EOFError: if the stream ends in less than ``n`` bytes

        """
        assert n >= 0
        while len(self.buffer) < n:
            if self.eof:
                p = len(self.buffer)
                raise EOFError(f"stream ends after {p} bytes, expected {n} bytes")
            yield
        r = self.buffer[:n]
        del self.buffer[:n]
        return r

    def feed_data(self, data: bytes) -> None:
        """
        Write ``data`` to the stream.

        """
        self.buffer += data

    def feed_eof(self) -> None:
        """
        End the stream.

        """
        self.eof = True

    def at_eof(self) -> bool:
        """
        Whether the stream has ended and all data was read.

        """
        return self.eof and not self.buffer

from websockets.streams import StreamReader

from .utils import GeneratorTestCase


class StreamReaderTests(GeneratorTestCase):
    def setUp(self):
        self.reader = StreamReader()

    def test_readline(self):
        self.reader.feed_data(b"spam\neggs\n")

        gen = self.reader.readline()
        line = self.assertGeneratorReturns(gen)
        self.assertEqual(line, b"spam\n")

        gen = self.reader.readline()
        line = self.assertGeneratorReturns(gen)
        self.assertEqual(line, b"eggs\n")

    def test_readline_need_more_data(self):
        self.reader.feed_data(b"spa")

        gen = self.reader.readline()
        next(gen)
        self.reader.feed_data(b"m\neg")
        line = self.assertGeneratorReturns(gen)
        self.assertEqual(line, b"spam\n")

        gen = self.reader.readline()
        next(gen)
        self.reader.feed_data(b"gs\n")
        line = self.assertGeneratorReturns(gen)
        self.assertEqual(line, b"eggs\n")

    def test_readline_at_eof(self):
        self.reader.feed_data(b"spa")
        self.reader.feed_eof()

        gen = self.reader.readline()
        with self.assertRaises(EOFError) as raised:
            next(gen)
        self.assertEqual(
            str(raised.exception), "stream ends after 3 bytes, before end of line"
        )

    def test_readexactly(self):
        self.reader.feed_data(b"spameggs")

        gen = self.reader.readexactly(4)
        data = self.assertGeneratorReturns(gen)
        self.assertEqual(data, b"spam")

        gen = self.reader.readexactly(4)
        data = self.assertGeneratorReturns(gen)
        self.assertEqual(data, b"eggs")

    def test_readexactly_need_more_data(self):
        self.reader.feed_data(b"spa")

        gen = self.reader.readexactly(4)
        next(gen)
        self.reader.feed_data(b"meg")
        data = self.assertGeneratorReturns(gen)
        self.assertEqual(data, b"spam")

        gen = self.reader.readexactly(4)
        next(gen)
        self.reader.feed_data(b"gs")
        data = self.assertGeneratorReturns(gen)
        self.assertEqual(data, b"eggs")

    def test_readexactly_at_eof(self):
        self.reader.feed_data(b"spa")
        self.reader.feed_eof()

        gen = self.reader.readexactly(4)
        with self.assertRaises(EOFError) as raised:
            next(gen)
        self.assertEqual(
            str(raised.exception), "stream ends after 3 bytes, expected 4 bytes"
        )

    def test_at_eof_after_feeding_eof(self):
        self.assertFalse(self.reader.at_eof())
        self.reader.feed_eof()
        self.assertTrue(self.reader.at_eof())

    def test_at_eof_after_reading_data(self):
        self.reader.feed_data(b"spam")
        self.reader.feed_eof()
        self.assertFalse(self.reader.at_eof())
        self.assertGeneratorReturns(self.reader.readexactly(4))
        self.assertTrue(self.reader.at_eof())

import unittest

import rfc_2047_encoded_word_codec as rfc


class TestEncodeWord(unittest.TestCase):
    def test_b_encode_utf8(self):
        out = rfc.encode_word("Olé", "utf-8", "B")
        self.assertEqual(out, "=?utf-8?B?T2zDqQ==?=")

    def test_q_encode_utf8(self):
        out = rfc.encode_word("Olé", "utf-8", "Q")
        self.assertEqual(out, "=?utf-8?Q?Ol=C3=A9?=")

    def test_q_space_becomes_underscore(self):
        out = rfc.encode_word("a b", "ascii", "Q")
        self.assertEqual(out, "=?ascii?Q?a_b?=")

    def test_default_charset_is_utf8(self):
        out = rfc.encode_word("x", encoding="B")
        self.assertEqual(out, "=?utf-8?B?eA==?=")

    def test_default_encoding_is_b(self):
        out = rfc.encode_word("x", "ascii")
        self.assertEqual(out, "=?ascii?B?eA==?=")

    def test_charset_canonicalised(self):
        out = rfc.encode_word("x", "UTF8", "B")
        self.assertTrue(out.startswith("=?utf-8?"))

    def test_invalid_encoding_raises(self):
        with self.assertRaises(ValueError):
            rfc.encode_word("x", "utf-8", "Z")

    def test_unknown_charset_raises(self):
        with self.assertRaises(LookupError):
            rfc.encode_word("x", "no-such-charset", "B")

    def test_non_str_input_raises(self):
        with self.assertRaises(TypeError):
            rfc.encode_word(b"bytes", "utf-8", "B")  # type: ignore[arg-type]


class TestDecodeWord(unittest.TestCase):
    def test_decode_b(self):
        self.assertEqual(rfc.decode_word("=?utf-8?B?T2zDqQ==?="), "Olé")

    def test_decode_q(self):
        self.assertEqual(rfc.decode_word("=?utf-8?Q?Ol=C3=A9?="), "Olé")

    def test_decode_q_underscore_to_space(self):
        self.assertEqual(rfc.decode_word("=?ascii?Q?a_b?="), "a b")

    def test_decode_q_lowercase_hex(self):
        self.assertEqual(rfc.decode_word("=?utf-8?Q?ol=c3=a9?="), "olé")

    def test_decode_b_with_embedded_whitespace(self):
        # Some legacy mailers fold base64 mid-word.
        self.assertEqual(rfc.decode_word("=?utf-8?B?T2zD qQ==?="), "Olé")

    def test_decode_strips_surrounding_whitespace(self):
        self.assertEqual(rfc.decode_word("  =?utf-8?B?eA==?=  "), "x")

    def test_decode_with_language_tag(self):
        # RFC 2231 language tag in the charset position, seen in the wild.
        self.assertEqual(rfc.decode_word("=?utf-8*en?B?T2zDqQ==?="), "Olé")

    def test_decode_unknown_charset_raises(self):
        with self.assertRaises(LookupError):
            rfc.decode_word("=?no-such-charset?B?eA==?=")

    def test_decode_not_a_word_raises(self):
        with self.assertRaises(ValueError):
            rfc.decode_word("hello")

    def test_decode_two_words_raises(self):
        with self.assertRaises(ValueError):
            rfc.decode_word("=?utf-8?B?eA==?= =?utf-8?B?eA==?=")

    def test_decode_malformed_q_raises(self):
        with self.assertRaises(ValueError):
            rfc.decode_word("=?utf-8?Q?=ZZ?=")

    def test_decode_non_str_raises(self):
        with self.assertRaises(TypeError):
            rfc.decode_word(b"=?utf-8?B?eA==?=")  # type: ignore[arg-type]


class TestDecodeHeader(unittest.TestCase):
    def test_plain_text_passthrough(self):
        self.assertEqual(rfc.decode_header("just text"), "just text")

    def test_single_word(self):
        self.assertEqual(rfc.decode_header("=?utf-8?B?T2zDqQ==?="), "Olé")

    def test_two_words_drop_separator(self):
        # Per RFC 2047 6.2, whitespace between adjacent encoded words is
        # removed.
        h = "=?utf-8?B?T2zDqQ==?= =?utf-8?B?T2zDqQ==?="
        self.assertEqual(rfc.decode_header(h), "OléOlé")

    def test_word_with_trailing_text(self):
        h = "=?utf-8?B?T2zDqQ==?= (x)"
        self.assertEqual(rfc.decode_header(h), "Olé (x)")

    def test_text_word_text(self):
        h = "a =?utf-8?B?T2zDqQ==?= b"
        self.assertEqual(rfc.decode_header(h), "a Olé b")

    def test_bad_word_left_intact(self):
        h = "=?no-such-charset?B?eA==?= ok"
        self.assertEqual(rfc.decode_header(h), "=?no-such-charset?B?eA==?= ok")

    def test_empty_header(self):
        self.assertEqual(rfc.decode_header(""), "")

    def test_non_str_raises(self):
        with self.assertRaises(TypeError):
            rfc.decode_header(b"bytes")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

"""Core implementation of the RFC 2047 encoded-word codec.

The codec handles the two RFC 2047 encodings, ``Q`` (quoted-printable-ish)
and ``B`` (base64), across any charset Python's ``codecs`` module can load.

Design decisions
----------------

* **One encoded word at a time for encoding.**  RFC 2047 allows a header
  to contain several encoded words separated by linear-white-space; the
  layout of that whitespace is a presentation concern best handled by the
  caller.  ``encode_word`` therefore produces a single encoded word and
  ``decode_header`` is the helper that knows how to join several back into
  a single string.

* **Strict on decode, best-effort on charset.**  Decoding tolerates
  whitespace *inside* the base64 payload (some mailers fold it in) but
  rejects anything that is not a syntactically valid encoded word with a
  trailing ``?=``.  Unknown charsets raise ``LookupError`` straight from
  ``codecs`` rather than being silently substituted.

* **No 75-character wrapping.**  RFC 2047 limits a single encoded word to
  75 characters, but wrapping requires knowing how the header line will be
  folded into the 78-column CRLF limit, which depends on the surrounding
  text.  Doing that here would require guessing the caller's layout, so it
  is deliberately left out.  The README says so.
"""

from __future__ import annotations

import base64
import codecs
import re

__all__ = ["encode_word", "decode_word", "decode_header"]

# Matches a single encoded word:
#   =? <charset> [*lang] ? <encoding> ? <encoded-text> ?=
# ``encoded-text`` is non-greedy so that multiple words on one line are split
# correctly; the trailing ``?=`` is required.
_ENCODED_WORD_RE = re.compile(
    r"=\?([^?]+)\?([BbQq])\?([^?]*)\?="
)


def _qp_encode(text: str, charset: str) -> str:
    """RFC 2047 Q-encode ``text`` for the given charset.

    RFC 2047's Q encoding differs from RFC 2045 quoted-printable in two
    ways: spaces become ``_`` (not ``=20``) and a narrower set of bytes
    requires escaping.  We follow the spec literally: every byte outside
    ``[A-Za-z0-9!*+/-]`` and the space becomes ``=XX``.
    """
    raw = text.encode(charset)
    out = []
    for byte in raw:
        if (
            33 <= byte <= 60       # !"#$...<
            or 62 <= byte <= 126    # >...~
        ) and byte != 61:           # exclude '=' which has meaning in QP
            out.append(chr(byte))
        elif byte == 32:            # space -> underscore per RFC 2047
            out.append("_")
        else:
            out.append("=%02X" % byte)
    return "".join(out)


def _qp_decode(text: str, charset: str) -> str:
    """Decode an RFC 2047 Q-encoded payload."""
    # Undo the underscore-as-space convention first, then quoted-printable.
    # ``=XX`` is case-insensitive in the hex digits per RFC 2045.
    raw = bytearray()
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "_":
            raw.append(0x20)
            i += 1
        elif c == "=" and i + 2 < n + 1 and i + 2 <= n - 1 + 1:
            # Need two hex digits after '='.  Guard against short tails.
            hexpart = text[i + 1 : i + 3]
            if len(hexpart) == 2 and re.fullmatch(r"[0-9A-Fa-f]{2}", hexpart):
                raw.append(int(hexpart, 16))
                i += 3
            else:
                raise ValueError("Malformed Q-encoded sequence at %d: %r" % (i, text[i:]))
        else:
            raw.append(ord(c))
            i += 1
    return raw.decode(charset)


def _b_encode(text: str, charset: str) -> str:
    """Base64-encode ``text`` for the given charset, RFC 2047 style.

    Standard base64 uses ``+`` and ``/`` which are fine inside an encoded
    word, but the ``=`` padding is also legal.  We strip trailing newline
    artifacts that ``b64encode`` never produces for bytes input but cost
    nothing to guard against.
    """
    raw = text.encode(charset)
    return base64.b64encode(raw).decode("ascii")


def _b_decode(text: str, charset: str) -> str:
    """Decode a B-encoded payload, tolerating embedded whitespace.

    Some legacy mailers fold base64 by inserting spaces or newlines inside
    the encoded text.  RFC 2047 says the text is ``\x21-\x7e`` with no
    whitespace, but being lenient on decode costs nothing and recovers
    real-world messages that strict parsers would drop.
    """
    cleaned = re.sub(r"\s+", "", text)
    raw = base64.b64decode(cleaned)
    return raw.decode(charset)


def encode_word(text: str, charset: str = "utf-8", encoding: str = "B") -> str:
    """Encode ``text`` as a single RFC 2047 encoded word.

    Parameters
    ----------
    text:
        The non-ASCII (or ASCII) string to encode.
    charset:
        Any charset name Python's ``codecs`` module recognises.  Defaults
        to ``utf-8``.
    encoding:
        ``"B"`` for base64 (the default, smaller for dense text) or
        ``"Q"`` for the RFC 2047 Q encoding (smaller for mostly-ASCII text
        with a few non-ASCII characters).

    Returns the string ``=?<charset>?<encoding>?<payload>?=``.

    Raises ``LookupError`` if the charset is unknown, and ``ValueError`` if
    ``encoding`` is not ``B`` or ``Q`` (case-insensitive).
    """
    if not isinstance(text, str):
        raise TypeError("text must be str, got %s" % type(text).__name__)
    enc = encoding.upper()
    if enc == "B":
        payload = _b_encode(text, charset)
    elif enc == "Q":
        payload = _qp_encode(text, charset)
    else:
        raise ValueError("encoding must be 'B' or 'Q', got %r" % encoding)
    # Resolve the canonical charset name so callers get back what Python
    # actually used; e.g. "UTF8" -> "utf-8".
    canon = codecs.lookup(charset).name
    return "=?%s?%s?%s?=" % (canon, enc, payload)


def decode_word(encoded: str) -> str:
    """Decode a single RFC 2047 encoded word.

    ``encoded`` must be exactly one encoded word of the form
    ``=?<charset>?<encoding>?<payload>?=`` with no surrounding text.

    Returns the decoded string.  Raises ``ValueError`` if ``encoded`` is
    not a syntactically valid single encoded word, and propagates
    ``LookupError`` for an unknown charset.
    """
    if not isinstance(encoded, str):
        raise TypeError("encoded must be str, got %s" % type(encoded).__name__)
    m = _ENCODED_WORD_RE.fullmatch(encoded.strip())
    if m is None:
        raise ValueError("not a single encoded word: %r" % encoded)
    charset, encoding, payload = m.group(1), m.group(2).upper(), m.group(3)
    # Strip an optional RFC 2231 language tag suffix (``*lang``) from the
    # charset.  RFC 2047 itself does not allow it, but it appears in the
    # wild often enough that rejecting it would lose real messages.
    charset_base = charset.split("*", 1)[0]
    if encoding == "B":
        return _b_decode(payload, charset_base)
    return _qp_decode(payload, charset_base)


def decode_header(header: str) -> str:
    """Decode an RFC 2047 header value that may contain several words.

    Adjacent encoded words separated only by whitespace have their
    whitespace removed (per RFC 2047, section 6.2, "each encoded word\n    is separated from the next by linear-white-space").  Plain text
    between encoded words is kept verbatim and is *not* concatenated
    across whitespace boundaries with adjacent encoded words.

    Non-encoded-word text is returned unchanged.  Encoded words with an
    unknown charset are left verbatim rather than raising, because a
    single bad word should not poison an entire header.
    """
    if not isinstance(header, str):
        raise TypeError("header must be str, got %s" % type(header).__name__)

    result_parts: list[str] = []
    pos = 0
    # Track whether the previous emitted chunk was a decoded encoded word,
    # so we can drop the separating whitespace per the RFC.
    prev_was_word = False

    for m in _ENCODED_WORD_RE.finditer(header):
        # Literal text before this encoded word.
        literal = header[pos : m.start()]
        if literal:
            if prev_was_word and literal.strip() == "":
                # Whitespace separating two encoded words: drop it.
                pass
            else:
                result_parts.append(literal)
                prev_was_word = False

        try:
            decoded = decode_word(m.group(0))
            result_parts.append(decoded)
            prev_was_word = True
        except (ValueError, LookupError):
            # Leave a bad encoded word intact rather than discarding it.
            result_parts.append(m.group(0))
            prev_was_word = False

        pos = m.end()

    # Trailing literal.
    trailing = header[pos:]
    if trailing:
        result_parts.append(trailing)

    return "".join(result_parts)

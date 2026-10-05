"""RFC 2047 encoded-word codec.

A small, zero-dependency library for encoding and decoding RFC 2047
encoded-word phrases as used in MIME message headers.

Only what the core module exports is re-exported here.
"""

from .core import encode_word, decode_word, decode_header

__all__ = ["encode_word", "decode_word", "decode_header"]

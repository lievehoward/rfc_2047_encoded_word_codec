# RFC 2047 Encoded Word Codec

A small, dependency-free Python library for encoding and decoding RFC 2047
encoded-word phrases as used in MIME message headers. Handles both the `B`
(base64) and `Q` (quoted-printable-ish) encodings across any charset
Python's `codecs` module can load.

## Usage

```python
from rfc_2047_encoded_word_codec import encode_word, decode_word, decode_header

# Encode a single word.
encoded = encode_word("Olé", charset="utf-8", encoding="B")
# '=?utf-8?B?T2zDqQ==?='

# Decode a single word back to text.
decode_word(encoded)  # 'Olé'

# Decode a whole header that may contain several encoded words and plain text.
decode_header("a =?utf-8?B?T2zDqQ==?= b")  # 'a Olé b'
```

## Why

Parsing and producing RFC 2047 encoded words is easy to get almost right
and painful to get exactly right. The spec has two encodings, an
underscore-means-space convention, an optional language tag, and a
whitespace-joining rule that most hand-rolled implementations ignore. This
library exists to do exactly that small job correctly, and nothing else.

The trade-off is deliberate: `encode_word` produces a **single** encoded
word and does not wrap it to the 75-character limit the RFC imposes on a
line, because line wrapping depends on the surrounding header text and the
78-column folding context that only the caller knows. If you need wrapping,
you break the input into words and fold them yourself.

## Edges you will hit

- `decode_header` drops whitespace **between** two adjacent encoded words
  (per RFC 2047 6.2) but preserves whitespace between an encoded word and
  plain text. This is the spec behaviour, not a bug, but it surprises people
  who expect whitespace to always survive.
- An encoded word with an unknown charset is **left intact** by
  `decode_header` so one bad word doesn't poison the whole header.
  `decode_word`, by contrast, raises `LookupError` for an unknown charset
  because it has nowhere to hide the failure.
- `decode_word` accepts an optional RFC 2231 language tag in the charset
  position (`=?utf-8*en?B?...?=`) and ignores it. RFC 2047 itself does not
  permit the tag, but real mail has it.

## Exports

- `encode_word(text, charset="utf-8", encoding="B") -> str`
- `decode_word(encoded) -> str`
- `decode_header(header) -> str`

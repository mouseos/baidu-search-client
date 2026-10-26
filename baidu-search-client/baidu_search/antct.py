# -*- coding: utf-8 -*-
"""
Generation of the ``ant_ct`` token for Baidu search URLs, as
implemented by the Baidu Android app (com.baidu.searchbox 15.57.1.10).

Specification, from the app code:

  - Java side: ``bq0.m.h(String)`` (SearchUrlGenerator, classes12)
        text = "t=" + DateTimeUtil.getCalibratedTime()
             + "&w=" + zk9.c.c(query.getBytes(), false)
        ant_ct = URLEncoder.encode(EncryptDecryptUtils.encrypt(text), "UTF-8")
  - ``w``: ``zk9.c.c(byte[], boolean)`` (classes13) is the MD5 digest
    as a hex string (lowercase when the second argument is false).
  - ``encrypt`` is the JNI function
    ``Java_com_baidu_searchbox_encrypt_decrypt_EncryptDecryptUtils_encrypt``
    in libAntctEncrypt.so.

Key and IV: fixed values built into the app; they do not depend on
the device, the user, or the time.  The JNI code base64-decodes two
44-character literals from .rodata and passes the first 16 bytes of
each decoded value (32 bytes each) to ``AES::MakeKey`` as key and IV
(keyLen = blockLen = 0x10).  The decoded literals have the form
"ASCII string + NUL + another string"; only the first 16 bytes are
used.  ``KEY_B64_LITERAL`` / ``IV_B64_LITERAL`` below hold those
literals, and the decode-then-take-16-bytes step follows the app.

Cipher (the ``AES::Encrypt`` mode=1 path): AES-128-CBC with PKCS#7
padding.  Pad length = 16 - (len % 16), i.e. a full block when the
length is a multiple of 16; each pad byte equals the pad length.
The output is base64-encoded, and the Java side then URL-encodes it.

The ``t`` value: ``DateTimeUtil.getCalibratedTime()`` (classes12) is
``String.valueOf((System.currentTimeMillis() / 1000) + mDelta)``, so
the unit is seconds.  ``mDelta`` is a calibration offset in seconds,
derived from a server time string by ``setDeltaTime(String)``; it is
0 when uncalibrated.  This module takes ``t`` as an argument and
callers pass seconds.  The encryption itself is a deterministic
function of the plaintext.
"""

import base64
import hashlib
import urllib.parse

from Crypto.Cipher import AES

# Base64 literals from libAntctEncrypt.so (.rodata), 44 chars each.
KEY_B64_LITERAL = "aGVsbF9iYWlkX2JveGFwcABib3hhcHBfYmFpZF9oZWw="
IV_B64_LITERAL = "Ym94YXBwX2JhaWRfaGVsbABPYmplY3Qgbm90IEluaXQ="

# As in the app: the first 16 bytes of each decoded literal.
_KEY = base64.b64decode(KEY_B64_LITERAL)[:16]
_IV = base64.b64decode(IV_B64_LITERAL)[:16]

BLOCK = 16


def md5_hex_lower(data: bytes) -> str:
    """zk9.c.c(byte[], false): MD5 digest as a lowercase hex string."""
    return hashlib.md5(data).hexdigest()


def build_plaintext(calibrated_time_ms, query: str) -> str:
    """
    The plaintext assembled by bq0.m.h().

    The app uses query.getBytes() (the platform default charset).
    Android's default is UTF-8, so the query is encoded as UTF-8 here
    too.  The time value is in seconds (see the module docstring).
    """
    w = md5_hex_lower(query.encode("utf-8"))
    return "t={}&w={}".format(calibrated_time_ms, w)


def _pkcs7_pad(data: bytes) -> bytes:
    """The JNI padding: pad_len = 16 - (len % 16); each pad byte = pad_len."""
    pad_len = BLOCK - (len(data) % BLOCK)
    return data + bytes([pad_len]) * pad_len


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data or len(data) % BLOCK != 0:
        raise ValueError("invalid padded length")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > BLOCK:
        raise ValueError("invalid padding")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("invalid padding bytes")
    return data[:-pad_len]


def antct_encrypt(plaintext: str) -> str:
    """
    EncryptDecryptUtils.encrypt(String): encrypt the UTF-8 bytes of
    the input with AES-128-CBC/PKCS#7 and return base64.  The Java
    side's URLEncoder step is the caller's responsibility.
    """
    data = _pkcs7_pad(plaintext.encode("utf-8"))
    ct = AES.new(_KEY, AES.MODE_CBC, _IV).encrypt(data)
    return base64.b64encode(ct).decode("ascii")


def antct_decrypt(b64_ciphertext: str) -> str:
    """Decrypt an ant_ct value (base64) back to its plaintext."""
    ct = base64.b64decode(b64_ciphertext)
    pt = AES.new(_KEY, AES.MODE_CBC, _IV).decrypt(ct)
    return _pkcs7_unpad(pt).decode("utf-8")


def make_ant_ct(calibrated_time_ms, query: str) -> str:
    """
    The whole of bq0.m.h(): assemble the plaintext, encrypt it, and
    URL-encode the result.  The return value is the (encoded) value
    of the ant_ct URL parameter.

    Java's URLEncoder differs from quote_plus in general (it encodes
    spaces as '+', for example), but base64 output only contains
    [A-Za-z0-9+/=], so quote_plus(safe='') is equivalent here
    ('+' -> %2B, '/' -> %2F, '=' -> %3D).
    """
    text = build_plaintext(calibrated_time_ms, query)
    enc = antct_encrypt(text)
    return urllib.parse.quote_plus(enc, safe="")

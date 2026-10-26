# -*- coding: utf-8 -*-
"""
ant_ct 生成処理の Python 独立実装
対象: Baidu公式Androidアプリ com.baidu.searchbox 15.57.1.10

再現元 (APK静的解析の確定事項):
  - Java 側: bq0.m.h(String) (SearchUrlGenerator, classes12)
        text = "t=" + DateTimeUtil.getCalibratedTime()
             + "&w=" + zk9.c.c(query.getBytes(), false)
        ant_ct = URLEncoder.encode(EncryptDecryptUtils.encrypt(text), "UTF-8")
  - w: zk9.c.c(byte[], boolean) (classes13)
        = MessageDigest.getInstance("MD5") の digest を16進文字列化
          (第2引数 false のとき小文字)
  - encrypt: libAntctEncrypt.so の JNI
        Java_com_baidu_searchbox_encrypt_decrypt_EncryptDecryptUtils_encrypt
        (REA/Ghidra デコンパイル: logs/rea-decompile-antct-encrypt.log)

鍵・IV の生成元と依存関係:
  端末・ユーザー・時刻には一切依存しない「APK内蔵の固定値」である。
  JNI 本体は .rodata 内の 44 文字 Base64 リテラル 2 本を base64_decode し、
    鍵     = リテラル1 のデコード結果(32B)の先頭16バイト
    IV     = リテラル2 のデコード結果(32B)の先頭16バイト
  を AES::MakeKey(key, chain, keyLen=0x10, blockLen=0x10) へ渡す。
  リテラル文字列そのものは難読化を兼ねており、デコードすると
  ASCII 文字列 + NUL + 別文字列 という形になる (先頭16Bのみが有効)。
  下記 KEY_B64_LITERAL / IV_B64_LITERAL はその .rodata リテラルを
  そのまま保持したもので、デコード→先頭16B の手順もAPKどおりに再現する。

暗号処理 (AES::Encrypt mode=1 の構造):
  AES-128-CBC, PKCS#7 パディング
    パディング長 = 16 - (len % 16)  (len が16の倍数なら16のフルブロック)
    パディングバイト値 = パディング長
  出力は base64_encode した文字列。Java 側でさらに URLEncoder される。

t (校正時刻) について:
  DateTimeUtil.getCalibratedTime() (classes12) は
    String.valueOf((System.currentTimeMillis() / 1000) + mDelta)
  であり、単位は「秒」である (mDelta は setDeltaTime(String) で
  サーバ時刻文字列から算出される校正オフセット・秒。未校正時は 0)。
  本実装では t を引数として受け取る (呼び出し側が秒単位で与える)。
  ant_ct の暗号部分そのものは t の値に依存しない決定的変換である。
  【変更履歴 2026-10-25 追加検証】当初版は「ミリ秒」と誤記し、
  前回プローブはミリ秒値を t に渡していた。APKコード確認により
  秒単位へ訂正した (crypto-independent-validation.md 参照)。
"""

import base64
import hashlib
import urllib.parse

from Crypto.Cipher import AES

# libAntctEncrypt.so .rodata 内の Base64 リテラル (44文字 x 2)
# 根拠: logs/rea-decompile-antct-encrypt.log の擬似コード
KEY_B64_LITERAL = "aGVsbF9iYWlkX2JveGFwcABib3hhcHBfYmFpZF9oZWw="
IV_B64_LITERAL = "Ym94YXBwX2JhaWRfaGVsbABPYmplY3Qgbm90IEluaXQ="

# APK の手順どおり: デコード結果の先頭16バイトが鍵 / IV
_KEY = base64.b64decode(KEY_B64_LITERAL)[:16]
_IV = base64.b64decode(IV_B64_LITERAL)[:16]

BLOCK = 16


def md5_hex_lower(data: bytes) -> str:
    """zk9.c.c(byte[], false): MD5 digest の16進文字列 (小文字)"""
    return hashlib.md5(data).hexdigest()


def build_plaintext(calibrated_time_ms, query: str) -> str:
    """
    bq0.m.h() の平文組立。
    注意: APK では query.getBytes() (プラットフォーム既定文字セット) を使う。
    Android の既定は UTF-8 のため、ここでも UTF-8 で符号化する。
    """
    w = md5_hex_lower(query.encode("utf-8"))
    return "t={}&w={}".format(calibrated_time_ms, w)


def _pkcs7_pad(data: bytes) -> bytes:
    """JNI 本体のパディング: pad_len = 16 - (len % 16), 各バイト = pad_len"""
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
    EncryptDecryptUtils.encrypt(String) の再現。
    入力文字列を UTF-8 バイト列として AES-128-CBC/PKCS#7 で暗号化し、
    Base64 文字列を返す (Java 側の URLEncoder は呼び出し側の責務)。
    """
    data = _pkcs7_pad(plaintext.encode("utf-8"))
    ct = AES.new(_KEY, AES.MODE_CBC, _IV).encrypt(data)
    return base64.b64encode(ct).decode("ascii")


def antct_decrypt(b64_ciphertext: str) -> str:
    """検証用: ant_ct (Base64) を復号して平文に戻す。"""
    ct = base64.b64decode(b64_ciphertext)
    pt = AES.new(_KEY, AES.MODE_CBC, _IV).decrypt(ct)
    return _pkcs7_unpad(pt).decode("utf-8")


def make_ant_ct(calibrated_time_ms, query: str) -> str:
    """
    bq0.m.h() 全体の再現: 平文組立 → JNI暗号化 → URLEncoder.encode。
    返り値が URL パラメータ ant_ct の値 (符号化済み) になる。
    Java の URLEncoder は空白を '+' にする等の差異があるが、
    Base64 出力に現れる文字は [A-Za-z0-9+/=] のみで、
    quote_plus(safe='') と等価になる ('+'→%2B, '/'→%2F, '='→%3D)。
    """
    text = build_plaintext(calibrated_time_ms, query)
    enc = antct_encrypt(text)
    return urllib.parse.quote_plus(enc, safe="")

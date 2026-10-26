# Provenance and licensing notes

This document records where the implementation came from and how the
intellectual-property questions were evaluated before publication. It
is part of the publication record.

## What this software is

An independent Python reimplementation of the web-search flow used by
the Baidu Android app (`com.baidu.searchbox`, version 15.57.1.10). The
behavior was determined by static analysis (decompilation) of the
publicly distributed APK and verified with a small number of anonymous
requests against the live service. The software is not an official
Baidu product or API.

## Evaluation by category

### 1. Original code written for this project

All Python code in `baidu_search/` and `baidu_parser/`, the tests, and
the documentation were written for this project. That code is released
under the MIT License (see the repository `LICENSE`).

### 2. General algorithms and formats

AES-128-CBC, MD5, PKCS#7 padding, Base64, URL encoding, HTTP, cookies,
and HTML parsing are public, standardized techniques. Using them is
not, by itself, a barrier to redistribution; standard implementations
come from the `pycryptodome` and `lxml` dependencies.

### 3. Constants and formats learned from the APK

The search URL template, parameter names and formats (including the
`pu` parameter structure), the result-HTML template names used for
classification, and the two Base64 literals from which the `ant_ct`
AES key and IV are derived were learned by analyzing the APK.

About the `ant_ct` key/IV specifically:

- They are **fixed literals compiled into the publicly distributed
  APK binary** (in the native library's read-only data). Every copy of
  the app contains the same values; they are not tied to any user,
  account, or device.
- They are **not authentication credentials**: they grant no access to
  any account, and the `ant_ct` plaintext they protect is only a
  timestamp plus the MD5 of the search query — no user data.
- Their role is an obfuscated client-side integrity token. Reproducing
  them is comparable to documenting an undocumented request format.
- This evaluation does **not** rest on "the value is in the APK, so it
  cannot be a secret" alone: the decisive points are that the values
  are identical for all installations, are not associated with any
  person, and protect no confidential information. Separately,
  reproducing undocumented behavior may conflict with the service's
  terms of use; that is a terms-of-service consideration, not a
  secrecy one, and users of this code should review the terms that
  apply to them.

### 4. Direct copies of third-party source code

None. No source code from the APK or from any other third-party
software was copied into this repository. The implementation was
written in Python from the observed behavior. Decompiler output
(jadx/Ghidra) is not included. The files under
`baidu-search-client/tests/legacy_reference/` are this project's own
earlier validation probes, included as test references.

### 5. Values that are actual authentication secrets

None are included. The repository contains no account credentials, no
access tokens, no real cookie values, no proxy credentials, and no
personal data. Test fixtures are excerpts of HTML that the service
served to anonymous requests, with session-identifying parameter
values (`ant_ct`, `rsv_pq`, `rsv_t`, `rqid`) replaced by `REDACTED`
before inclusion (see `baidu-search-parser/tests/make_fixtures.py`).
The fixtures necessarily contain snippets of third-party web content
(the search results themselves); they are retained at the minimum
size needed to test the parser.

## Scope of the MIT License

The MIT License covers only the original code and documentation in
this repository. It does not grant any rights in Baidu's app,
services, trademarks, or content, and nothing here should be read as
applying MIT terms to them.

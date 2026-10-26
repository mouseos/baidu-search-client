# Legacy reference probes (test support only)

`crypto.py` and `search_probe.py` in this directory are verbatim copies of
the original validation probes written during the reverse-engineering
project (they lived in the development workspace under
`work/python-validation/`). They are **not** part of the library and are
never imported by runtime code paths.

They are kept so the test-suite can keep proving that the implementations
vendored into the package (`baidu_search/antct.py`,
`baidu_search/urlbuild.py`) produce byte-identical output to the code that
was validated against the real service:

- `tests/test_search_url.py`
- `tests/test_packaging_consistency.py`

Both files are original code written for this project and are covered by
the repository's MIT License. `search_probe.py` also contains the classic
suggest URL builder that the client does not use; it is retained only as
the historical reference implementation.

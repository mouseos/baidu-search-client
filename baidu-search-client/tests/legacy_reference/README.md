# Reference copies (test support only)

`crypto.py` and `search_probe.py` in this directory are copies of the
original implementations from which `baidu_search/antct.py` and
`baidu_search/urlbuild.py` were taken. They are not part of the
library and are never imported by runtime code paths.

The test suite uses them to check that the package implementations
produce byte-identical output:

- `tests/test_search_url.py`
- `tests/test_packaging_consistency.py`

Both files are original code written for this project and are covered
by the repository's MIT License. `search_probe.py` also contains the
classic suggest URL builder, which the client does not use; it is
kept as a reference only.

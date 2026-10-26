# Development

## Building wheels

```bash
python3 -m pip install build
python3 -m build --outdir dist baidu-search-parser
python3 -m build --outdir dist baidu-search-client
```

This produces `baidu_parser-1.0.0` and `baidu_search-1.0.0` wheels
(and sdists) under `dist/`.

## Installing from built wheels

`baidu-parser` is not on PyPI, so pip needs the local `dist`
directory as a package source:

```bash
python3 -m pip install --find-links dist baidu-search
```

`baidu-parser` is resolved from `./dist` automatically. To install
only the parser:

```bash
python3 -m pip install --find-links dist baidu-parser
```

The same commands work with the prebuilt wheels attached to the
[v1.0.0 release](https://github.com/mouseos/baidu-search-client/releases/tag/v1.0.0):
download both wheel files into one directory and pass that directory
to `--find-links`.

## Running the tests

Both suites run offline (HTTP is mocked; parsing uses bundled
fixtures):

```bash
python3 -m pip install pytest
python3 -m pytest baidu-search-parser/tests -q   # 31 tests
python3 -m pytest baidu-search-client/tests -q   # 65 tests
```

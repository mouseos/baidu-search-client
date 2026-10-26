"""Search-URL generation entry points for the client.

Since round 18 the validated URL builder and ``ant_ct`` live
**inside** this package (:mod:`baidu_search.urlbuild` and
:mod:`baidu_search.antct`, vendored verbatim from
``work/python-validation/search_probe.py`` / ``crypto.py``).  This
module is the stable adapter the rest of the client uses:

* :func:`build_initial_search_url` delegates 1:1 to
  ``urlbuild.build_search_url`` — the canonical reproduction of the
  APK's ``bq0.m`` (SearchUrlGenerator) +
  ``BaiduIdentityManager.processWebSearchUrl`` behaviour (default web
  template, ``KWD<millis>`` placeholder replaced by the
  Java-URLEncoder-encoded query, the statically reproducible ``pu``
  merges ``osname=baiduboxapp`` / ``cfrom=<tnconfig>`` /
  ``csrc=app_mainbox_txt``, ``https`` upgrade, ``ant_ct`` and the
  fixed ``t_samp``).
* No parameter that the validated code does not produce is added.
  Parameters that depend on device / runtime state (cuid, cua, from,
  pkgname, …) stay absent, exactly as in the successful anonymous
  measurements.

Time handling for ``ant_ct``: the APK's
``DateTimeUtil.getCalibratedTime()`` returns *seconds* since epoch
plus a server-calibration offset ``mDelta``.  The offset cannot be
observed from Python, so — as in the validated probes — the current
Unix time in **seconds** is used with ``mDelta = 0``.  This is an
approximation and is recorded as such (the millisecond value is only
used for the ``KWD`` placeholder, exactly as the APK does; a former
millisecond-based ``t`` was a bug that was corrected in the
validation round and must not be revived).

:func:`_load_legacy` below is **development/test support only**: it
loads the original validation probe by path so the test-suite can
prove the vendored code still produces byte-identical output.  No
runtime code path in this package calls it, and the installed
package works where the validation directory does not exist.
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path
from types import ModuleType
from typing import Optional

from . import urlbuild

_legacy_module: Optional[ModuleType] = None


def user_agent() -> str:
    """The User-Agent string used by the validated probes.

    The device-specific part of ``http.agent`` is a representative
    value, as documented in ``urlbuild`` (and in the original
    ``search_probe.py``).
    """
    return urlbuild.USER_AGENT


def build_initial_search_url(query: str, now_ms: Optional[int] = None) -> str:
    """Build the first-page search URL for ``query``.

    Delegates 1:1 to the vendored ``urlbuild.build_search_url``
    (which internally passes ``now_ms // 1000`` — seconds — as the
    ``ant_ct`` time).  ``now_ms`` exists only so tests can pin the
    clock; production callers leave it ``None``.
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    return urlbuild.build_search_url(query, now_ms)


# ---------------------------------------------------------------------------
# Development/test support only — NOT used by any runtime code path.
# ---------------------------------------------------------------------------

def _legacy_validation_dir() -> Path:
    """Locate the original validation probes (test support only).

    Resolution order: ``BAIDU_LEGACY_VALIDATION_DIR``, then the
    development workspace layout (``work/python-validation/``), then
    the reference copies vendored with the test-suite in this
    repository (``tests/legacy_reference/``).
    """
    env = os.environ.get("BAIDU_LEGACY_VALIDATION_DIR")
    if env:
        return Path(env)
    # <analysis>/baidu-search-client/baidu_search/search_url.py
    dev_dir = Path(__file__).resolve().parent.parent.parent / "work" / "python-validation"
    if (dev_dir / "search_probe.py").exists():
        return dev_dir
    return Path(__file__).resolve().parent.parent / "tests" / "legacy_reference"


def _load_legacy() -> ModuleType:
    """Import the original ``search_probe.py`` by path (tests only).

    Kept so ``tests/test_search_url.py`` can assert byte-identical
    output between the vendored implementation and the validated
    probe.  Raises :class:`ImportError` when neither the development
    workspace copy nor the reference copy vendored under
    ``tests/legacy_reference/`` exists.
    """
    global _legacy_module
    if _legacy_module is not None:
        return _legacy_module
    legacy_dir = _legacy_validation_dir()
    probe_path = legacy_dir / "search_probe.py"
    if not probe_path.exists():
        raise ImportError(
            "validated search_probe.py not found at {} "
            "(development workspace only)".format(probe_path)
        )
    spec = importlib.util.spec_from_file_location(
        "baidu_legacy_search_probe", probe_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    _legacy_module = module
    return module

"""Search-URL generation entry points for the client.

This module is the adapter the rest of the client uses:

* :func:`build_initial_search_url` delegates to
  ``urlbuild.build_search_url``, which reproduces the URL built by
  the app's ``bq0.m`` (SearchUrlGenerator) and
  ``BaiduIdentityManager.processWebSearchUrl``: the default web
  template, the ``KWD<millis>`` placeholder replaced by the
  Java-URLEncoder-encoded query, the statically determined ``pu``
  merges ``osname=baiduboxapp`` / ``cfrom=<tnconfig>`` /
  ``csrc=app_mainbox_txt``, the ``https`` upgrade, ``ant_ct``, and
  the fixed ``t_samp``.
* No parameter beyond that set is added.  Parameters that depend on
  device or runtime state (cuid, cua, from, pkgname, …) stay absent,
  because their values cannot be determined outside the app.

Time handling for ``ant_ct``: the app's
``DateTimeUtil.getCalibratedTime()`` returns seconds since epoch plus
a server-calibration offset (``mDelta``).  The offset cannot be
observed from Python, so the current Unix time in seconds is used
with ``mDelta = 0``; this is an approximation.  Milliseconds are
used only for the ``KWD`` placeholder, as in the app; the ``ant_ct``
time itself is in seconds.

:func:`_load_legacy` below is test support only: it loads the
reference implementation by path so the test suite can check that
this package produces byte-identical output.  No runtime code path
calls it.
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
    """The User-Agent sent with requests.

    The device-specific part of ``http.agent`` is a representative
    value (see ``urlbuild``).
    """
    return urlbuild.USER_AGENT


def build_initial_search_url(query: str, now_ms: Optional[int] = None) -> str:
    """Build the first-page search URL for ``query``.

    Delegates to ``urlbuild.build_search_url``, which passes
    ``now_ms // 1000`` (seconds) as the ``ant_ct`` time.  ``now_ms``
    exists only so tests can pin the clock; production callers leave
    it ``None``.
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    return urlbuild.build_search_url(query, now_ms)


# ---------------------------------------------------------------------------
# Test support only — not used by any runtime code path.
# ---------------------------------------------------------------------------

def _legacy_validation_dir() -> Path:
    """Locate the reference implementation (test support only).

    Resolution order: ``BAIDU_LEGACY_VALIDATION_DIR``, then the
    development layout (``work/python-validation/`` next to this
    repository), then the reference copy bundled with the test suite
    (``tests/legacy_reference/``).
    """
    env = os.environ.get("BAIDU_LEGACY_VALIDATION_DIR")
    if env:
        return Path(env)
    # <parent of this repository>/work/python-validation
    dev_dir = Path(__file__).resolve().parent.parent.parent / "work" / "python-validation"
    if (dev_dir / "search_probe.py").exists():
        return dev_dir
    return Path(__file__).resolve().parent.parent / "tests" / "legacy_reference"


def _load_legacy() -> ModuleType:
    """Import the reference ``search_probe.py`` by path (tests only).

    Used by ``tests/test_search_url.py`` to assert byte-identical
    output between this package and the reference implementation.
    Raises :class:`ImportError` when no reference copy is found.
    """
    global _legacy_module
    if _legacy_module is not None:
        return _legacy_module
    legacy_dir = _legacy_validation_dir()
    probe_path = legacy_dir / "search_probe.py"
    if not probe_path.exists():
        raise ImportError(
            "reference search_probe.py not found at {}".format(probe_path)
        )
    spec = importlib.util.spec_from_file_location(
        "baidu_legacy_search_probe", probe_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    _legacy_module = module
    return module

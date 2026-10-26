"""CLI tests (offline --from-html mode exercises the real pipeline;
live mode is covered by the mocked client tests and the one measured
live run recorded in integration-test-report.md).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT.parent / "baidu-search-parser" / "tests" / "fixtures" / "tianqi_p1.html"


def _run_cli(args, **kwargs):
    return subprocess.run(
        [sys.executable, "-m", "baidu_search", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        **kwargs,
    )


def test_cli_offline_to_file(tmp_path):
    out = tmp_path / "results.json"
    proc = _run_cli(
        [
            "--from-html", str(FIXTURE),
            "--query", "天气",
            "--output", str(out),
            "--verbose",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["query"] == "天气"
    assert data["pages_fetched"] == 1
    assert len(data["results"]) == 5
    # file content is human-readable UTF-8, not \uXXXX soup
    assert "天气" in out.read_text(encoding="utf-8")
    assert "pages_fetched=1" in proc.stderr


def test_cli_offline_to_stdout():
    proc = _run_cli(["--from-html", str(FIXTURE), "--query", "天气"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["pages_fetched"] == 1
    assert len(data["cards"]) == 4


def test_cli_main_function_offline(tmp_path):
    from baidu_search.cli import main

    out = tmp_path / "r.json"
    rc = main(
        [
            "--from-html", str(FIXTURE),
            "--query", "天气",
            "--output", str(out),
        ]
    )
    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8"))["pages_fetched"] == 1

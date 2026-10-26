import json
import subprocess
import sys
from pathlib import Path

from conftest import FIXTURES, ROOT


def test_cli_converts_fixture(tmp_path):
    out = tmp_path / "results.json"
    proc = subprocess.run(
        [
            sys.executable, "-m", "baidu_parser",
            "--input", str(FIXTURES / "tianqi_p1.html"),
            "--query", "天气",
            "--output", str(out),
        ],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["query"] == "天气"
    assert len(data["results"]) == 5
    assert data["page"]["next_pn"] == 10


def test_cli_stdout(tmp_path):
    proc = subprocess.run(
        [
            sys.executable, "-m", "baidu_parser",
            "--input", str(FIXTURES / "weather_en.html"),
            "--query", "weather",
        ],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert len(data["cards"]) == 6

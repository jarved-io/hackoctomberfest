"""Regenerate data/python/requests/<version>.json from real pinned installs.

Usage: python scripts/generate_snapshots.py 2.25.1 2.28.2 2.31.0 2.32.3
Each version is pip-installed (--no-deps) into a temp dir and introspected, so the
snapshots are derived from the library itself, not written by hand or by an LLM.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "python" / "requests"
OUT.mkdir(parents=True, exist_ok=True)

for ver in sys.argv[1:] or ["2.31.0"]:
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--no-deps",
                               "--break-system-packages", "--target", td, f"requests=={ver}"])
        env = dict(os.environ, PYTHONPATH=td)
        raw = subprocess.check_output(
            [sys.executable, str(ROOT / "scripts" / "introspect_requests.py")], env=env)
    data = json.loads(raw)
    assert data["version"] == ver, (data["version"], ver)
    snap = {
        "schema_version": 1,
        "language": "python",
        "library": "requests",
        "version": ver,
        "generated_by": "scripts/generate_snapshots.py (inspect.signature on the real package)",
        "api_count": len(data["apis"]),
        "apis": data["apis"],
    }
    (OUT / f"{ver}.json").write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n")
    print(f"requests {ver}: {len(data['apis'])} symbols")

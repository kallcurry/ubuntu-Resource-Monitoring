"""Verify the standalone payload without Python/virtualenv paths on PATH."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--x11", action="store_true")
    args = parser.parse_args()
    executable = args.executable.resolve()
    env = dict(os.environ)
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "CONDA_PREFIX", "LD_LIBRARY_PATH",
                 "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    env["PATH"] = "/usr/bin:/bin"
    env["QT_QPA_PLATFORM"] = "xcb" if args.x11 else "offscreen"
    version = subprocess.check_output([str(executable), "--version"], env=env, text=True, timeout=20)
    assert "Pulse Monitor" in version, version
    raw = subprocess.check_output([str(executable), "--diagnose"], env=env, text=True, timeout=30)
    diagnosis = json.loads(raw)
    assert diagnosis["threads"] >= 1 and diagnosis["memory_bytes"] > 0, diagnosis
    with tempfile.TemporaryDirectory(prefix="pulse-package-test-") as temporary:
        result = subprocess.run(
            [str(executable), "--config-dir", temporary, "--quit-after", "3"], env=env,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + "\n" + result.stderr)
        assert "Traceback (most recent call last)" not in result.stderr, result.stderr
    print("Standalone version, real diagnostics, GUI startup and clean shutdown passed")


if __name__ == "__main__":
    main()

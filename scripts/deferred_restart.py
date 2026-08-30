#!/usr/bin/env python3
"""Restart Hermes only after the current chat response has been sent."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def wait_for_response_sent(log_path: Path, offset: int, timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if log_path.exists():
            with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(min(offset, log_path.stat().st_size))
                if "Sending response" in handle.read():
                    return True
        time.sleep(1)
    return False


def restart_gateway(label: str) -> int:
    if sys.platform == "darwin" and shutil.which("launchctl"):
        target = f"gui/{os.getuid()}/{label}"
        return subprocess.run(
            ["launchctl", "kickstart", "-k", target], check=False
        ).returncode

    hermes = shutil.which("hermes")
    if not hermes:
        print("Hermes executable not found; restart was not attempted.", flush=True)
        return 1
    return subprocess.run([hermes, "gateway", "restart"], check=False).returncode


def worker(log_path: Path, offset: int, timeout: int, label: str, lock: Path) -> int:
    try:
        if not wait_for_response_sent(log_path, offset, timeout):
            print("Timed out before a response was sent; restart cancelled.", flush=True)
            return 1
        time.sleep(5)
        return restart_gateway(label)
    finally:
        lock.unlink(missing_ok=True)


def schedule(log_path: Path, timeout: int, label: str, lock: Path) -> int:
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print("A deferred Hermes restart is already scheduled.")
        return 0
    os.close(fd)

    offset = log_path.stat().st_size if log_path.exists() else 0
    worker_log = log_path.parent / "deferred-restart.log"
    output = worker_log.open("a", encoding="utf-8")
    try:
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--log",
                str(log_path),
                "--offset",
                str(offset),
                "--timeout",
                str(timeout),
                "--label",
                label,
                "--lock",
                str(lock),
            ],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    except Exception:
        lock.unlink(missing_ok=True)
        raise
    finally:
        output.close()

    print("Deferred restart scheduled; send the final chat response now.")
    return 0


def main() -> int:
    home = Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--log", type=Path, default=home / "logs" / "gateway.log")
    parser.add_argument("--offset", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--label", default="ai.hermes.gateway")
    parser.add_argument("--lock", type=Path, default=home / ".deferred-restart.lock")
    args = parser.parse_args()
    if args.worker:
        return worker(args.log, args.offset, args.timeout, args.label, args.lock)
    return schedule(args.log, args.timeout, args.label, args.lock)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""SwiftBar plugin showing Codex five-hour and weekly usage."""

# <xbar.title>Codex Usage</xbar.title>
# <xbar.version>1.0.0</xbar.version>
# <xbar.author>Steve Folly</xbar.author>
# <xbar.desc>Shows Codex five-hour and weekly rate-limit usage.</xbar.desc>
# <xbar.dependencies>python3,codex</xbar.dependencies>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>

from __future__ import annotations

import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time
from datetime import datetime
from typing import Any


TIMEOUT_SECONDS = 8
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
CACHE_PATH = (
    Path.home()
    / "Library"
    / "Caches"
    / "SwiftBarCodexUsage"
    / "rate-limits.json"
)
NOTIFICATION_STATE_PATH = CACHE_PATH.with_name("notifications.json")
NOTIFICATION_THRESHOLD = 90
# Temporary testing switch: set to False to restore once-per-window alerts.
NOTIFICATION_TEST_MODE = False


def find_codex() -> str:
    override = os.environ.get("CODEX_CLI_PATH")
    candidates = [
        override,
        shutil.which("codex"),
        str(Path.home() / "homebrew" / "bin" / "codex"),
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
        str(Path.home() / ".local" / "bin" / "codex"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError(
        "Codex CLI not found. Install it or set CODEX_CLI_PATH in SwiftBar."
    )


def send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def receive(process: subprocess.Popen[str], request_id: int) -> dict[str, Any]:
    assert process.stdout is not None
    deadline = time.monotonic() + TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        remaining = max(0, deadline - time.monotonic())
        ready, _, _ = select.select([process.stdout], [], [], remaining)
        if not ready:
            break

        line = process.stdout.readline()
        if not line:
            break

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        if message.get("id") == request_id:
            if "error" in message:
                raise RuntimeError(str(message["error"]))
            return message

    raise TimeoutError("Timed out waiting for the Codex app-server")


def query_usage() -> dict[str, Any]:
    process = subprocess.Popen(
        [find_codex(), "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    try:
        send(
            process,
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "swiftbar-codex-usage",
                        "title": "SwiftBar Codex Usage",
                        "version": "1.0.0",
                    }
                },
            },
        )
        receive(process, 1)
        send(process, {"method": "initialized"})
        send(
            process,
            {"id": 2, "method": "account/rateLimits/read", "params": {}},
        )
        message = receive(process, 2)
        limits = message["result"]["rateLimits"]
        save_cache(limits)
        return limits
    finally:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()


def save_cache(limits: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"savedAt": time.time(), "rateLimits": limits}),
        encoding="utf-8",
    )
    temporary.replace(CACHE_PATH)


def load_cache() -> tuple[dict[str, Any], datetime] | None:
    try:
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        saved_at = float(cached["savedAt"])
        if time.time() - saved_at > CACHE_MAX_AGE_SECONDS:
            return None
        return cached["rateLimits"], datetime.fromtimestamp(saved_at).astimezone()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def clamp_percent(value: Any) -> int:
    return max(0, min(100, round(float(value))))


def notify_usage(limits: dict[str, Any]) -> None:
    """Notify once per reset window, persisting state across refreshes."""
    try:
        state = json.loads(NOTIFICATION_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}

    for key, label in (("primary", "Five-hour"), ("secondary", "Weekly")):
        window = limits[key]
        reset = window["resetsAt"]
        if not NOTIFICATION_TEST_MODE and float(window["usedPercent"]) < NOTIFICATION_THRESHOLD:
            continue
        if not NOTIFICATION_TEST_MODE and state.get(key) == reset:
            continue
        message = (
            f"{label} usage has reached {clamp_percent(window['usedPercent'])}%.\n"
            f"Resets {reset_text(reset)}."
        )
        try:
            subprocess.run(
                [
                    "osascript", "-e",
                    f'display notification {json.dumps(message)} with title "Codex Usage"',
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TIMEOUT_SECONDS,
            )
            if NOTIFICATION_TEST_MODE:
                continue
            state[key] = reset
            NOTIFICATION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = NOTIFICATION_STATE_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(state), encoding="utf-8")
            temporary.replace(NOTIFICATION_STATE_PATH)
        except (OSError, subprocess.SubprocessError):
            # Notification failures must not prevent the usage display.
            continue


def colour(percent: int) -> str:
    if percent >= 85:
        return "#E5484D"
    if percent >= 60:
        return "#F5A524"
    return "#30A46C"


def reset_text(timestamp: Any) -> str:
    reset = datetime.fromtimestamp(float(timestamp)).astimezone()
    now = datetime.now().astimezone()
    seconds = max(0, int((reset - now).total_seconds()))

    if seconds < 60:
        relative = "in less than a minute"
    elif seconds < 60 * 60:
        relative = f"in {seconds // 60}m"
    elif seconds < 24 * 60 * 60:
        hours, remainder = divmod(seconds, 60 * 60)
        minutes = remainder // 60
        relative = f"in {hours}h {minutes}m"
    else:
        days, remainder = divmod(seconds, 24 * 60 * 60)
        hours = remainder // (60 * 60)
        relative = f"in {days}d {hours}h"

    return f"{relative} ({reset.strftime('%a %-d %b, %H:%M')})"


def progress_bar(percent: int, width: int = 20) -> str:
    filled = round(width * percent / 100)
    return "\u25cf" * filled + "\u25cb" * (width - filled)


def render(limits: dict[str, Any], cached_at: datetime | None = None) -> None:
    primary = limits["primary"]
    secondary = limits["secondary"]
    five_hour = clamp_percent(primary["usedPercent"])
    weekly = clamp_percent(secondary["usedPercent"])
    worst = max(five_hour, weekly)

    stale_marker = " \u26a0" if cached_at else ""
    indicator_colour = "#F5A524" if cached_at else colour(worst)
    print(
        f"5h {five_hour}% \u00b7 7d {weekly}%{stale_marker}"
        f" | color={indicator_colour} sfimage=gauge.with.dots.needle.67percent"
    )
    print("---")
    print("Codex usage | size=14")
    print(f"Five-hour window: {five_hour}% used | color={colour(five_hour)}")
    print(f"{progress_bar(five_hour)}  {100 - five_hour}% remaining | font=Menlo size=11")
    print(f"Resets {reset_text(primary['resetsAt'])} | size=11")
    print("---")
    print(f"Weekly window: {weekly}% used | color={colour(weekly)}")
    print(f"{progress_bar(weekly)}  {100 - weekly}% remaining | font=Menlo size=11")
    print(f"Resets {reset_text(secondary['resetsAt'])} | size=11")
    print("---")
    print(f"Plan: {str(limits.get('planType') or 'unknown').title()}")
    if cached_at:
        print(
            "Showing cached data "
            f"from {cached_at.strftime('%a %-d %b, %H:%M:%S')}"
            " | color=#E5484D"
        )
    print("Refresh now | refresh=true")


def render_error(error: Exception) -> None:
    print("Codex ? | color=#888888 sfimage=exclamationmark.triangle")
    print("---")
    print("Codex usage unavailable | color=#E5484D")
    safe_message = str(error).replace("|", "-").replace("\n", " ")
    print(f"{safe_message} | color=#888888 size=11")
    print("Refresh now | refresh=true")


def main() -> int:
    try:
        limits = query_usage()
        notify_usage(limits)
        render(limits)
    except Exception as error:
        cached = load_cache()
        if cached:
            limits, cached_at = cached
            render(limits, cached_at)
        else:
            render_error(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())

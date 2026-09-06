#!/usr/bin/env python3
"""Monitor an iOS TestFlight public beta link and send a Telegram notification
when the beta starts accepting new testers.

Configuration is read from a .env file (see .env.example). Run once with
`python3 monitor.py` (e.g. from cron) or as a long-running loop with
`python3 monitor.py --loop`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / ".tf_state.json"

# Phrases Apple shows on the public join page when the beta is NOT joinable.
# If none of these appear (and the page looks like a valid TestFlight page),
# we treat the beta as open for new testers.
FULL_MARKERS = (
    "This beta is full.",
    "This beta isn't accepting any new testers right now.",
    "This beta has stopped accepting new testers.",
    "This beta isn’t accepting any new testers right now.",  # curly apostrophe
)

# A marker that confirms we actually loaded a TestFlight join page (and not an
# error/redirect page), so we don't mistake a broken fetch for "available".
PAGE_MARKERS = ("Join the", "beta", "TestFlight")


def load_env(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments, optional quotes."""
    if not path.exists():
        sys.exit(f"Missing config file: {path}\nCopy .env.example to .env and fill it in.")
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # Don't clobber values already set in the real environment.
        os.environ.setdefault(key, val)


def require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        sys.exit(f"Required config '{name}' is missing or empty in .env")
    return val


def fetch(url: str, timeout: int) -> str:
    headers = {
        # TestFlight serves different markup to bots; a desktop UA gets the
        # human-facing page with the "beta is full" copy.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def beta_app_name(html: str) -> str:
    m = re.search(r"Join the (.+?) beta", html)
    if m:
        return m.group(1).strip()
    m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else "TestFlight beta"


def check_availability(html: str) -> tuple[bool, str]:
    """Return (is_available, reason)."""
    if not any(marker in html for marker in PAGE_MARKERS):
        return False, "unexpected page content (not a TestFlight join page?)"
    for marker in FULL_MARKERS:
        if marker in html:
            return False, marker
    return True, "no 'full' marker found — slots appear open"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except OSError as exc:
        print(f"[warn] could not write state file: {exc}", file=sys.stderr)


def send_telegram(token: str, chat_id: str, text: str, timeout: int) -> None:
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        api,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()


def run_once(cfg: dict) -> None:
    url = cfg["url"]
    state = load_state()
    was_available = state.get("available", False)

    try:
        html = fetch(url, cfg["timeout"])
    except requests.RequestException as exc:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] fetch failed: {exc}", file=sys.stderr)
        return

    available, reason = check_availability(html)
    app = beta_app_name(html)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {app}: {'AVAILABLE' if available else 'unavailable'} ({reason})")

    # Only notify on the transition from unavailable -> available, to avoid spam.
    if available and not was_available:
        msg = (
            f"🎉 <b>TestFlight slot open!</b>\n\n"
            f"<b>{app}</b> is now accepting new testers.\n\n"
            f"👉 <a href=\"{url}\">{url}</a>\n\n"
            f"<i>Checked at {stamp}</i>"
        )
        try:
            send_telegram(cfg["tg_token"], cfg["tg_chat_id"], msg, cfg["timeout"])
            print(f"[{stamp}] Telegram notification sent.")
        except requests.RequestException as exc:
            error = str(exc).replace(cfg["tg_token"], "<redacted>")
            print(f"[{stamp}] Telegram send failed: {error}", file=sys.stderr)
            return  # don't flip state, so we retry next run

    save_state({"available": available, "reason": reason, "checked_at": stamp})


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor TestFlight beta availability.")
    parser.add_argument("--loop", action="store_true", help="run continuously")
    parser.add_argument("--env", default=str(HERE / ".env"), help="path to .env file")
    args = parser.parse_args()

    load_env(Path(args.env))
    cfg = {
        "url": require("TF_URL"),
        "tg_token": require("TG_BOT_TOKEN"),
        "tg_chat_id": require("TG_CHAT_ID"),
        "interval": int(os.environ.get("CHECK_INTERVAL", "300")),
        "timeout": int(os.environ.get("HTTP_TIMEOUT", "20")),
    }

    if not args.loop:
        run_once(cfg)
        return

    print(f"Monitoring {cfg['url']} every {cfg['interval']}s. Ctrl-C to stop.")
    while True:
        run_once(cfg)
        try:
            time.sleep(cfg["interval"])
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()

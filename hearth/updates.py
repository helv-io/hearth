"""Is there a newer Hearth? One request to GitHub, at most once a day.

The only thing sent is that request. It carries no device data and no id. A
failure of any kind, offline, rate limited or an odd answer, means no popup.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from hearth import __version__
from hearth.paths import config_dir

# The one place that names the project. Everything below is built from it.
REPO = "helv-io/hearth"
TAGS_URL = f"https://api.github.com/repos/{REPO}/tags?per_page=100"
DOWNLOAD_PAGE = f"https://github.com/{REPO}/releases/latest"

TIMEOUT_SECONDS = 5
CHECK_EVERY_SECONDS = 24 * 60 * 60

# Semantic versions only: major.minor.patch, an optional pre-release such as
# -rc1 or rc1, and optional build metadata after a plus sign.
_VERSION = re.compile(
    r"^v?(?P<nums>\d+\.\d+\.\d+)(?:[-.]?(?P<pre>[A-Za-z][0-9A-Za-z.-]*))?(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True)
class Version:
    numbers: tuple[int, ...]
    pre: str = ""

    @property
    def is_release(self) -> bool:
        return not self.pre

    def sort_key(self):
        # A release sorts after its own pre-releases, 0.5.0rc1 < 0.5.0.
        return (self.numbers, 1 if self.is_release else 0, _natural(self.pre))

    def __str__(self):
        text = ".".join(str(n) for n in self.numbers)
        return f"{text}-{self.pre}" if self.pre else text


def _natural(text: str):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text.lower()) if p]


def parse(text: str, require_v: bool = False) -> Version | None:
    """A version like 0.5.0, v0.5.0 or 0.5.0-rc1. Anything else is None."""
    text = (text or "").strip()
    if require_v and not text.startswith("v"):
        return None
    found = _VERSION.match(text)
    if not found:
        return None
    numbers = tuple(int(n) for n in found.group("nums").split("."))
    return Version(numbers, found.group("pre") or "")


def is_dev_build(current: str) -> bool:
    """No version, an unreadable one, or a development marker."""
    parsed = parse(current)
    if parsed is None:
        return True
    if "dev" in parsed.pre.lower():
        return True
    return not any(parsed.numbers)


def newest_release(tags: list[str]) -> Version | None:
    """The highest v-tag that is a full release. Pre-releases and other tags are ignored."""
    best: Version | None = None
    for tag in tags:
        found = parse(tag, require_v=True)
        if found is None or not found.is_release:
            continue
        if best is None or found.sort_key() > best.sort_key():
            best = found
    return best


def is_newer(latest: str, current: str) -> bool:
    new, now = parse(latest), parse(current)
    if new is None or now is None:
        return False
    return new.sort_key() > now.sort_key()


# --- the saved choices and the last answer -------------------------------


def _path():
    return config_dir() / "updates.json"


def load_state() -> dict:
    state = {"enabled": True, "last_check": 0.0, "latest": "", "skipped": ""}
    try:
        stored = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    if not isinstance(stored, dict):
        return state
    if isinstance(stored.get("enabled"), bool):
        state["enabled"] = stored["enabled"]
    last = stored.get("last_check")
    if isinstance(last, (int, float)) and not isinstance(last, bool):
        state["last_check"] = float(last)
    for key in ("latest", "skipped"):
        if isinstance(stored.get(key), str):
            state[key] = stored[key]
    return state


def save_state(state: dict) -> None:
    try:
        _path().write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass  # a read-only folder only means we ask again next time


def set_enabled(enabled: bool) -> dict:
    state = load_state()
    state["enabled"] = bool(enabled)
    save_state(state)
    return state


def skip(version: str) -> dict:
    state = load_state()
    state["skipped"] = version
    save_state(state)
    return state


# --- asking GitHub ------------------------------------------------------


class Unreachable(Exception):
    """No answer at all, such as offline. Worth asking again soon."""


def _secure_context() -> ssl.SSLContext:
    """Trust the same certificate list everywhere.

    A Python bundled into an app on macOS may not find the system list, which
    would make every check fail. certifi comes with pymobiledevice3 (through requests).
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def fetch_tags() -> list[str]:
    request = urllib.request.Request(
        TAGS_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Hearth/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=_secure_context()) as reply:
            data = json.loads(reply.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ValueError(f"GitHub answered {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise Unreachable(str(error)) from error
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    return [row["name"] for row in data if isinstance(row, dict) and isinstance(row.get("name"), str)]


def due(state: dict, now: float) -> bool:
    last = state.get("last_check", 0.0)
    return last > now or now - last >= CHECK_EVERY_SECONDS


def offer(current: str = __version__, now: float | None = None, fetch=None) -> str:
    """The version to tell the person about, or an empty string.

    Asks GitHub when the last answer is a day old. Otherwise the saved answer is
    used, so a person who said Not now sees it again next start without a request.
    """
    now = time.time() if now is None else now
    fetch = fetch or fetch_tags
    try:
        state = load_state()
        if not state["enabled"] or is_dev_build(current):
            return ""
        if due(state, now):
            try:
                latest = newest_release(fetch())
            except Unreachable:
                pass  # offline: do not count it, ask again next start
            except Exception:
                state["last_check"] = now  # rate limit or a bad answer: wait a day
                save_state(state)
            else:
                state["last_check"] = now
                if latest is not None:
                    state["latest"] = str(latest)
                save_state(state)
        latest_text = state["latest"]
        if not latest_text or not is_newer(latest_text, current):
            return ""
        if state["skipped"] and not is_newer(latest_text, state["skipped"]):
            return ""
        return latest_text
    except Exception:
        return ""

"""Is there a newer Hearth? One request to GitHub at every start, and one when asked.

The only thing sent is that request. It carries no device data and no id. At
start, a failure of any kind, offline, rate limited or an odd answer, means no
popup. When the person asks with the button, a failure is reported in plain words.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from hearth import __version__
from hearth.net import secure_context
from hearth.paths import config_dir

# The one place that names the project. Everything below is built from it.
REPO = "helv-io/hearth"
TAGS_URL = f"https://api.github.com/repos/{REPO}/tags?per_page=100"
DOWNLOAD_PAGE = f"https://github.com/{REPO}/releases/latest"

TIMEOUT_SECONDS = 5

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
    state = {"enabled": True, "latest": "", "skipped": ""}
    try:
        stored = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    if not isinstance(stored, dict):
        return state
    if isinstance(stored.get("enabled"), bool):
        state["enabled"] = stored["enabled"]
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


def fetch_tags() -> list[str]:
    request = urllib.request.Request(
        TAGS_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Hearth/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=secure_context()) as reply:
            data = json.loads(reply.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ValueError(f"GitHub answered {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise Unreachable(str(error)) from error
    if not isinstance(data, list):
        raise ValueError("unexpected answer")
    return [row["name"] for row in data if isinstance(row, dict) and isinstance(row.get("name"), str)]


def offer(current: str | None = None, fetch=None) -> str:
    """The version to tell the person about at start, or an empty string.

    Asks GitHub every time. When it cannot answer, the last answer it got is used,
    so a person who said Not now still sees it. A version they skipped stays quiet.
    """
    current = __version__ if current is None else current
    fetch = fetch or fetch_tags
    try:
        state = load_state()
        if not state["enabled"] or is_dev_build(current):
            return ""
        try:
            latest = newest_release(fetch())
        except Exception:
            pass  # offline, rate limited or an odd answer: say nothing
        else:
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


# What a check made on request found.
NEWER = "newer"
CURRENT = "current"
FAILED = "failed"


def check_now(current: str | None = None, fetch=None) -> tuple[str, str]:
    """Ask right now, for the Check for updates button.

    Returns (NEWER, version), (CURRENT, "") or (FAILED, ""). It ignores the startup
    setting and a skipped version, because the person asked. It never raises.
    """
    current = __version__ if current is None else current
    fetch = fetch or fetch_tags
    try:
        latest = newest_release(fetch())
        if latest is None:
            return FAILED, ""
        state = load_state()
        state["latest"] = str(latest)
        save_state(state)
        if is_newer(str(latest), current):
            return NEWER, str(latest)
        return CURRENT, ""
    except Exception:
        return FAILED, ""

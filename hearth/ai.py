"""Chat client. Grok and the OpenAI-compatible presets speak chat completions.
Anthropic is translated to the Messages API, the same split skgate uses.

The reply is streamed, and the call only fails when the model has been silent
too long. A model that thinks before it writes gets a long first wait, and a
model that has started writing gets a shorter one. Every piece that arrives
starts the clock again. A server that does not stream is asked again without
streaming. Reasoning is asked to be low, because the answer is structured JSON.
A provider that refuses either request is asked again without it, and Hearth
remembers that until it closes.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass
from http.client import HTTPException
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request

from hearth.grok_sso import CLI_HEADERS, FALLBACK_BASE
from hearth.layout import active_screen, catalog, current_outline, proposal_from_text
from hearth.net import open_url

# Silence before the first word, silence between words, and the most time one answer may take.
FIRST_IDLE = 180.0
BETWEEN_IDLE = 60.0
OVERALL_CAP = 600.0
# Listing models is a plain short request.
LIST_TIMEOUT = 30.0
MAX_REPLY = 8 << 20
EFFORT = "low"


@dataclass(frozen=True)
class Limits:
    first: float = FIRST_IDLE
    between: float = BETWEEN_IDLE
    cap: float = OVERALL_CAP


class Cancelled(Exception):
    """The person stopped the request."""


class _HttpError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"The model endpoint returned {status}. {detail[:280]}")
        self.status = status
        self.detail = detail


# What a provider has refused during this run, by endpoint and model.
_refused: dict[str, set[tuple[str, str]]] = {"effort": set(), "stream": set()}


def forget_refusals() -> None:
    for names in _refused.values():
        names.clear()


def _span(seconds: float) -> str:
    whole = max(1, round(seconds))
    if whole % 60 == 0:
        minutes = whole // 60
        return f"{minutes} minute" + ("" if minutes == 1 else "s")
    return f"{whole} second" + ("" if whole == 1 else "s")


def _system() -> str:
    grid = active_screen()
    cells = grid.columns * grid.rows
    return f"""You reorganize an iPhone or iPad home screen. Reply with one JSON object and nothing else.

Schema:
{{"summary":"one sentence","dock":["id"],"pages":[["id",{{"name":"Folder","apps":["id"]}}]]}}

Rules:
- Use every id in the catalog exactly once. Do not invent ids.
- dock holds at most {grid.dock} ids. Those ids are apps or shortcuts, never widgets, never folders.
- Each page is a list. A string is an app, a shortcut, or a widget. An object is a folder.
- A page has {grid.columns} columns and {grid.rows} rows, {cells} cells. An app or shortcut or folder costs 1 cell. A widget's cost is its "cells" value (4, 8, or 16). The items on a page must fit. A widget that does not fit on the rest of a row wraps to the next row.
- Folders hold apps and shortcuts only. Never put a widget in a folder. More than 9 apps spill onto extra pages inside the folder. Keep going. Do not make an empty folder.
- Shortcuts are web clips. Treat them as apps that belong beside the thing they open.
- Follow the user's instruction. Where the instruction is silent, keep the current grouping.

Popularity hints:
- Each catalog row has "where", the place it sits now. People keep what they use most in the dock, then on page 1, and nearer the first items of a page. Treat that as a popularity hint. Keep the most used apps easy to reach: dock first, then page 1, then early places.
- Some rows also have "data_mb" (size of the app's saved data), "app_mb" (the app's own size) and "owned_since" (year and month it was first obtained). A lot of saved data can mean heavy use. How long it has been owned says little. These are weak hints. The user's instruction comes first.
"""


def list_models(base_url: str, key: str, adapter: str = "", oauth: bool = False) -> list[str]:
    if adapter == "anthropic":
        payload = _anthropic_request(base_url, key, "models?limit=1000", None)
    else:
        payload = _openai_request(base_url, key, "models", None, oauth)
    rows = []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("models") or []
    ids = []
    for row in rows:
        if isinstance(row, str):
            ids.append(row)
        elif isinstance(row, dict) and row.get("id"):
            ids.append(str(row["id"]))
    return sorted(set(ids))


def organize(base_url: str, key: str, model: str, instruction: str, state, adapter: str = "", oauth: bool = False,
             cancel: Event | None = None, progress=None, limits: Limits | None = None, facts: dict | None = None) -> dict:
    if not model:
        raise RuntimeError("Pick an LLM model.")
    instruction = " ".join(instruction.split())
    if not instruction:
        raise RuntimeError("Say how you want it organized.")
    user = (
        "The user wants this:\n"
        f"{instruction}\n\n"
        "Current layout:\n"
        f"{json.dumps(current_outline(state), ensure_ascii=False)}\n\n"
        "Catalog:\n"
        f"{json.dumps(catalog(state, facts), ensure_ascii=False)}\n\n"
        "Follow the user's request. The rules still apply: every id once, "
        "widgets stay out of folders and out of the dock, and each page fits in "
        f"{active_screen().columns * active_screen().rows} cells."
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system()},
            {"role": "user", "content": user},
        ],
    }
    mark = (base_url.strip().rstrip("/").lower(), model)
    if adapter != "anthropic":
        body["response_format"] = {"type": "json_object"}
        if mark not in _refused["effort"]:
            body["reasoning_effort"] = EFFORT
    if mark not in _refused["stream"]:
        body["stream"] = True
    cancel = cancel or Event()
    limits = limits or Limits()
    while True:
        try:
            payload = _chat(base_url, key, body, adapter, oauth, cancel, progress, limits)
            break
        except _HttpError as exc:
            if not _adjust(body, exc, mark):
                raise
    content = _message_text(payload)
    if not content.strip():
        raise RuntimeError("The model returned an empty reply.")
    try:
        return proposal_from_text(content)
    except ValueError as exc:
        raise RuntimeError("The model's answer could not be read as a layout. Try again.") from exc


def _adjust(body: dict, exc: _HttpError, mark: tuple[str, str]) -> bool:
    """Drop the one extra the provider turned down. False when nothing is left to drop."""
    if exc.status not in (400, 422):
        return False
    text = exc.detail.lower()
    if "reasoning_effort" in body and ("reasoning" in text or "effort" in text):
        del body["reasoning_effort"]
        _refused["effort"].add(mark)
        return True
    if body.get("stream") and "stream" in text:
        del body["stream"]
        _refused["stream"].add(mark)
        return True
    if "response_format" in body:
        del body["response_format"]
        return True
    return False


def _chat(base_url, key, body, adapter, oauth, cancel, progress, limits) -> dict:
    try:
        return _once(base_url, key, body, adapter, oauth, cancel, progress, limits)
    except _HttpError as exc:
        if adapter != "anthropic" and oauth and _fallback_status(exc) and _host(base_url) != _host(FALLBACK_BASE):
            return _once(FALLBACK_BASE, key, body, adapter, True, cancel, progress, limits)
        raise


def _once(base_url, key, body, adapter, oauth, cancel, progress, limits) -> dict:
    if adapter == "anthropic":
        payload = _exchange(base_url, key, "messages", _to_anthropic(body), False, True, cancel, progress, limits)
        return _from_anthropic(payload, str(body.get("model") or ""))
    return _exchange(base_url, key, "chat/completions", body, oauth, False, cancel, progress, limits)


def _openai_request(base_url: str, key: str, path: str, body: dict | None, oauth: bool) -> dict:
    try:
        return _request(base_url, key, path, body, oauth)
    except RuntimeError as exc:
        if oauth and _fallback_status(exc) and _host(base_url) != _host(FALLBACK_BASE):
            return _request(FALLBACK_BASE, key, path, body, True)
        raise


def _fallback_status(exc: RuntimeError) -> bool:
    text = str(exc)
    return "returned 402" in text or "returned 403" in text


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _to_anthropic(body: dict) -> dict:
    system = []
    messages = []
    for item in body.get("messages") or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content") if isinstance(item.get("content"), str) else ""
        if role in ("system", "developer"):
            if content:
                system.append(content)
            continue
        if role not in ("user", "assistant"):
            role = "user"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] = messages[-1]["content"] + "\n\n" + content
        else:
            messages.append({"role": role, "content": content or "."})
    if not messages:
        messages = [{"role": "user", "content": "."}]
    out = {"model": body.get("model") or "", "max_tokens": 4096, "messages": messages}
    if body.get("stream"):
        out["stream"] = True
    if system:
        out["system"] = "\n\n".join(system)
    return out


def _from_anthropic(payload: dict, model: str) -> dict:
    blocks = payload.get("content") if isinstance(payload, dict) else None
    text = []
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                text.append(block["text"])
    return {
        "choices": [{
            "message": {"role": "assistant", "content": "\n".join(text)},
        }],
        "model": (payload or {}).get("model") or model,
    }


def _anthropic_request(base_url: str, key: str, path: str, body: dict | None) -> dict:
    return _request(base_url, key, path, body, False, anthropic=True)


def _message_text(payload: dict) -> str:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not choices:
        raise RuntimeError("The model returned an empty reply.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    raise RuntimeError("The model returned an empty reply.")


def _build(base_url, key, path, body, oauth, anthropic, stream=False) -> Request:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "text/event-stream, application/json" if stream else "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if anthropic:
        headers["anthropic-version"] = "2023-06-01"
        if key:
            headers["x-api-key"] = key
    elif key:
        headers["Authorization"] = "Bearer " + key
    if oauth and _host(url).endswith("grok.com"):
        headers.update(CLI_HEADERS)
    return Request(url, data=data, headers=headers, method="GET" if data is None else "POST")


def _translate(exc: Exception, wait: float) -> Exception:
    """Turn a failure to connect or to get the first answer into a plain message."""
    if isinstance(exc, HTTPError):
        try:
            detail = exc.read(1000).decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        return _HttpError(exc.code, detail)
    if isinstance(exc, URLError):
        if isinstance(exc.reason, TimeoutError):
            return RuntimeError(f"The model did not answer for {_span(wait)}.")
        return RuntimeError(f"Could not reach the endpoint. {exc.reason}")
    if isinstance(exc, TimeoutError):
        return RuntimeError(f"The model did not answer for {_span(wait)}.")
    return exc


def _request(base_url: str, key: str, path: str, body: dict | None, oauth: bool = False, anthropic: bool = False,
             timeout: float = LIST_TIMEOUT):
    """One plain request and its whole JSON reply, with a short limit."""
    request = _build(base_url, key, path, body, oauth, anthropic)
    try:
        with open_url(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise _translate(exc, timeout) from exc


class _Watch:
    """Cuts the connection when the model has been silent too long, when the whole answer takes too long,
    or when the person cancels. A cut makes the blocked read return at once."""

    def __init__(self, response, cancel: Event, limits: Limits, started: float):
        self.cancel = cancel
        self.limits = limits
        self.started = started
        self.last = time.monotonic()
        self.got_first = False
        self.complete = False
        self.reason: str | None = None
        self._done = Event()
        self._sock = _socket_of(response)
        if self._sock is not None:
            try:
                self._sock.settimeout(limits.cap + 5)  # the watch decides, not the socket
            except OSError:
                pass
        self._thread = threading.Thread(target=self._run, name="model-watch", daemon=True)
        self._thread.start()

    def touch(self) -> None:
        self.last = time.monotonic()

    def first_word(self) -> None:
        self.got_first = True

    def stop(self) -> None:
        self._done.set()
        self._thread.join(1)

    def _run(self) -> None:
        while not self._done.wait(0.05):
            now = time.monotonic()
            if self.cancel.is_set():
                self._cut("cancelled")
            elif now - self.started > self.limits.cap:
                self._cut("cap")
            elif now - self.last > (self.limits.between if self.got_first else self.limits.first):
                self._cut("idle")
            if self.reason:
                return

    def _cut(self, why: str) -> None:
        self.reason = why
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def explain(self, exc: BaseException | None) -> Exception:
        if self.reason == "cancelled" or self.cancel.is_set():
            return Cancelled()
        if self.reason == "cap":
            return RuntimeError(f"The model was still going after {_span(self.limits.cap)}, so Hearth stopped it.")
        if self.reason == "idle" or isinstance(exc, TimeoutError):
            if self.got_first:
                return RuntimeError(f"The model went quiet for {_span(self.limits.between)} partway through its answer.")
            return RuntimeError(f"The model did not answer for {_span(self.limits.first)}.")
        return RuntimeError("The connection to the model was lost partway through its answer.")


def _socket_of(response):
    try:
        return response.fp.raw._sock
    except AttributeError:
        return None


def _exchange(base_url, key, path, body, oauth, anthropic, cancel, progress, limits) -> dict:
    """Send one chat request and return the provider's reply as one JSON object, built from the stream when there is one."""
    request = _build(base_url, key, path, body, oauth, anthropic, stream=bool(body.get("stream")))
    if cancel.is_set():
        raise Cancelled()
    started = time.monotonic()
    try:
        response = open_url(request, timeout=limits.first)
    except Exception as exc:
        if cancel.is_set():
            raise Cancelled() from exc
        raise _translate(exc, limits.first) from exc
    with response:
        if cancel.is_set():
            raise Cancelled()
        watch = _Watch(response, cancel, limits, started)
        try:
            payload = _read(response, anthropic, progress, watch)
        except (OSError, HTTPException, ValueError) as exc:
            raise watch.explain(exc) from exc
        finally:
            watch.stop()
        if watch.reason and not watch.complete:
            raise watch.explain(None)
        return payload


def _read(response, anthropic: bool, progress, watch: _Watch) -> dict:
    kind = (response.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in kind:
        return _assemble(_lines(response, watch), anthropic, progress, watch)
    raw = response.read(MAX_REPLY + 1)
    if len(raw) > MAX_REPLY:
        raise RuntimeError("The model's reply was too long to read.")
    text = raw.decode("utf-8", errors="replace")
    if text.lstrip().startswith(("data:", "event:")):
        return _assemble(iter(text.splitlines()), anthropic, progress, watch)
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise RuntimeError("The model sent a reply Hearth could not read.") from exc
    watch.complete = True
    return payload


def _lines(response, watch: _Watch):
    total = 0
    while True:
        raw = response.readline(1 << 20)
        if not raw:
            return
        watch.touch()
        total += len(raw)
        if total > MAX_REPLY:
            raise RuntimeError("The model's reply was too long to read.")
        if watch.cancel.is_set():
            raise Cancelled()
        yield raw.decode("utf-8", errors="replace").strip()


def _sse_data(line: str) -> str | None:
    if not line.startswith("data:"):
        return None
    return line[5:].strip()


def _assemble(lines, anthropic: bool, progress, watch: _Watch) -> dict:
    """Join a stream of server-sent events into the same JSON a normal reply would have."""
    pieces: list[str] = []
    chars = 0
    reported = 0.0
    model = ""

    def heard(text: str, kept: bool) -> None:
        nonlocal chars, reported
        if not text:
            return
        watch.first_word()
        chars += len(text)
        if kept:
            pieces.append(text)
        now = time.monotonic()
        if progress is not None and now - reported > 0.4:
            reported = now
            progress(f"Asking the model… {chars:,} characters")

    for line in lines:
        data = _sse_data(line)
        if data is None:
            continue
        if data == "[DONE]":
            watch.complete = True
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        if not isinstance(chunk, dict):
            continue
        if anthropic:
            kind = chunk.get("type")
            if kind == "error" or chunk.get("error"):
                raise _HttpError(502, json.dumps(chunk.get("error") or chunk)[:1000])
            if kind == "message_start":
                model = str((chunk.get("message") or {}).get("model") or "")
            elif kind == "content_block_delta":
                delta = chunk.get("delta") or {}
                heard(delta.get("text") if isinstance(delta.get("text"), str) else "", True)
                heard(delta.get("thinking") if isinstance(delta.get("thinking"), str) else "", False)
            elif kind == "message_stop":
                watch.complete = True
                break
            continue
        if chunk.get("error"):
            raise _HttpError(502, json.dumps(chunk["error"])[:1000])
        model = model or str(chunk.get("model") or "")
        for choice in chunk.get("choices") or []:
            part = (choice.get("delta") or choice.get("message") or {}) if isinstance(choice, dict) else {}
            for name, kept in (("content", True), ("reasoning_content", False), ("reasoning", False)):
                value = part.get(name)
                heard(value if isinstance(value, str) else "", kept)
    text = "".join(pieces)
    if anthropic:
        return {"content": [{"type": "text", "text": text}], "model": model}
    return {"choices": [{"message": {"role": "assistant", "content": text}}], "model": model}

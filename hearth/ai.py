"""Chat client. Grok and the OpenAI-compatible presets speak chat completions.
Anthropic is translated to the Messages API, the same split skgate uses.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from hearth.grok_sso import CLI_HEADERS, FALLBACK_BASE
from hearth.layout import active_screen, catalog, current_outline, proposal_from_text
from hearth.net import secure_context


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


def organize(base_url: str, key: str, model: str, instruction: str, state, adapter: str = "", oauth: bool = False) -> dict:
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
        f"{json.dumps(catalog(state), ensure_ascii=False)}\n\n"
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
    if adapter != "anthropic":
        body["response_format"] = {"type": "json_object"}
    try:
        payload = _chat(base_url, key, body, adapter, oauth)
    except RuntimeError as exc:
        if adapter == "anthropic" or "400" not in str(exc) or "response_format" not in body:
            raise
        body.pop("response_format")
        payload = _chat(base_url, key, body, adapter, oauth)
    content = _message_text(payload)
    return proposal_from_text(content)


def _chat(base_url: str, key: str, body: dict, adapter: str, oauth: bool) -> dict:
    if adapter == "anthropic":
        return _anthropic_chat(base_url, key, body)
    return _openai_request(base_url, key, "chat/completions", body, oauth)


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


def _anthropic_chat(base_url: str, key: str, body: dict) -> dict:
    message = _to_anthropic(body)
    payload = _anthropic_request(base_url, key, "messages", message)
    return _from_anthropic(payload, str(body.get("model") or ""))


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


def _request(base_url: str, key: str, path: str, body: dict | None, oauth: bool = False, anthropic: bool = False):
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "iphone-layout"}
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
    request = Request(url, data=data, headers=headers, method="GET" if data is None else "POST")
    try:
        with urlopen(request, timeout=120, context=secure_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:280]
        raise RuntimeError(f"The model endpoint returned {exc.code}. {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach the endpoint. {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("The model endpoint timed out.") from exc

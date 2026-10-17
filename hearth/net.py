"""The one place Hearth opens a web connection, with one certificate setup for every request.

A Python bundled into an app on macOS may not find the system certificate list,
which would make every request to a model, to Grok sign-in, to the App Store
and to GitHub fail. certifi comes with pymobiledevice3, through requests. Its
list is added on top of the system list, so a company certificate that the
system already trusts keeps working.
"""

from __future__ import annotations

import ssl
import urllib.request
from functools import lru_cache


@lru_cache(maxsize=1)
def secure_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    try:
        import certifi

        context.load_verify_locations(cafile=certifi.where())
    except Exception:
        pass  # certifi missing or unreadable: the system list alone
    return context


def open_url(request: urllib.request.Request, *, timeout: float):
    """Open a request. Every web request in Hearth goes through here, so none can skip the certificate list.

    `timeout` is how long the connection and each read may stay silent, in seconds. The caller closes the reply.
    A ruff rule (TID251 in pyproject.toml) stops anything else from calling urlopen.
    """
    return urllib.request.urlopen(request, timeout=timeout, context=secure_context())

"""One certificate setup for every request Hearth makes.

A Python bundled into an app on macOS may not find the system certificate list,
which would make every request to a model, to Grok sign-in, to the App Store
and to GitHub fail. certifi comes with pymobiledevice3, through requests. Its
list is added on top of the system list, so a company certificate that the
system already trusts keeps working.
"""

from __future__ import annotations

import ssl
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

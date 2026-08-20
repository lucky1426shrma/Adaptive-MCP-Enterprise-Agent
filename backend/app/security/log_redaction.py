"""Defense-in-depth log redaction.

Structured logging discipline — never pass a secret into `extra=`, and
every place in this codebase that authenticates (bearer tokens, DB
connection strings, GitHub PATs, the OpenRouter API key) already
avoids logging the credential itself (see e.g.
`app/mcp/registry.py`'s auth middleware pattern, mirrored across every
MCP server) — is the PRIMARY defense here. This filter is a safety net
in case that discipline ever slips in a future change, not a
substitute for it: it redacts the VALUE of any log record attribute
whose NAME matches a known secret-like pattern.

LIMITATION, stated plainly: this cannot catch a secret embedded inside
a free-text log message string (e.g. `logger.info(f"token was {tok}")`)
— only attributes passed via `extra={...}` with a matching key name.
Avoiding that pattern remains a code-review discipline this filter
doesn't replace.
"""

from __future__ import annotations

import logging
import re

_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|token|password|secret|authorization|dsn|connection[_-]?string)",
    re.IGNORECASE,
)
_REDACTED = "***REDACTED***"

# Standard LogRecord attributes are never treated as secrets even if a
# name coincidentally matched (none currently do, but this guards
# against future stdlib additions colliding with the pattern above).
_NEVER_REDACT = {"msg", "args", "message"}


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in list(record.__dict__.items()):
            if key in _NEVER_REDACT:
                continue
            if isinstance(value, str) and _SECRET_KEY_PATTERN.search(key):
                setattr(record, key, _REDACTED)
        return True

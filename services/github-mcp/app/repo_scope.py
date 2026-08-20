"""Repository allow-list enforcement — pure logic, no I/O.

Split out from server.py specifically so it's unit-testable without any
dependency, and so the enforcement rule is auditable in one place: this
IS the least-privilege boundary for GitHub access. The caller (the LLM,
via the agent) can ask for any repository string it wants — this
function is what actually decides whether that request is honored,
independent of the request.
"""

from __future__ import annotations

from typing import List


def is_repository_allowed(repository: str, allowed_repositories: List[str]) -> bool:
    """Exact match only — deliberately no wildcard/prefix matching.

    An allow-list of `["myorg/payment-service"]` means exactly that
    repository, not `myorg/*` or anything containing that string. An
    empty allow-list denies everything (fail closed, not fail open) —
    a server that hasn't been explicitly told which repositories it may
    touch shouldn't touch any.
    """
    return repository in allowed_repositories

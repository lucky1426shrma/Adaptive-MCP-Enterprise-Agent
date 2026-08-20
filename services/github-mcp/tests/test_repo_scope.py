from __future__ import annotations

from app.repo_scope import is_repository_allowed


def test_exact_match_is_allowed() -> None:
    assert is_repository_allowed("myorg/payment-service", ["myorg/payment-service"]) is True


def test_repository_not_in_list_is_denied() -> None:
    assert is_repository_allowed("myorg/other-service", ["myorg/payment-service"]) is False


def test_empty_allowlist_denies_everything() -> None:
    assert is_repository_allowed("myorg/payment-service", []) is False


def test_match_is_case_sensitive() -> None:
    assert is_repository_allowed("MyOrg/Payment-Service", ["myorg/payment-service"]) is False


def test_no_prefix_matching() -> None:
    # "myorg/payment-service-v2" should NOT match an allow-list entry
    # for "myorg/payment-service" — exact match only.
    assert is_repository_allowed("myorg/payment-service-v2", ["myorg/payment-service"]) is False


def test_no_wildcard_matching() -> None:
    assert is_repository_allowed("myorg/anything", ["myorg/*"]) is False


def test_multiple_allowed_repositories() -> None:
    allowed = ["myorg/payment-service", "myorg/checkout-frontend"]
    assert is_repository_allowed("myorg/checkout-frontend", allowed) is True
    assert is_repository_allowed("myorg/unrelated-repo", allowed) is False

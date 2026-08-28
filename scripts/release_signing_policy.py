"""Local, fail-closed validation for commit and release-tag signers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


REGISTRY_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "maintainers"
    / "release-signing-keys.json"
)
RELEASE_TAG_FINGERPRINT = "1039EC488BE088997C1740D9ED0002B3562F2F59"
COMMIT_FINGERPRINT = "SHA256:TakAONGUVp2o/aQK9cJSncIDOZ3HEr27M6Ctr84LdGY"
_HEX40 = re.compile(r"^[0-9A-F]{40}$")
_SHA256 = re.compile(r"^SHA256:[A-Za-z0-9+/=]+$")


def _require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be boolean")
    return value


def _validate_registry(registry: dict[str, Any]) -> None:
    keys = registry.get("keys")
    if not isinstance(keys, list) or len(keys) != 1:
        raise ValueError("registry must contain exactly one release-tag key")
    key = keys[0]
    required_key = {
        "fingerprint", "algorithm", "public_key", "purpose", "trust_domain",
        "status", "valid_from", "expires", "may_sign_commits",
        "may_sign_release_tags",
    }
    if set(key) != required_key:
        raise ValueError("release-tag key fields are not exact")
    if not _HEX40.fullmatch(key["fingerprint"]):
        raise ValueError("release-tag fingerprint is invalid")
    if key["fingerprint"] != RELEASE_TAG_FINGERPRINT:
        raise ValueError("release-tag fingerprint mismatch")
    if key["purpose"] != "annotated LHE release tags":
        raise ValueError("release-tag purpose mismatch")
    if key["trust_domain"] != "release_tag":
        raise ValueError("release-tag trust domain mismatch")
    if _require_bool(key["may_sign_commits"], "may_sign_commits"):
        raise ValueError("release-tag signer cannot sign commits")
    if not _require_bool(key["may_sign_release_tags"], "may_sign_release_tags"):
        raise ValueError("release-tag signer must sign release tags")
    if key["status"] != "active" or not isinstance(key["public_key"], str):
        raise ValueError("release-tag key metadata is invalid")

    policy = registry.get("commit_signer_policy")
    required_policy = {
        "fingerprint", "purpose", "trust_domain", "source",
        "independent_verification", "may_sign_commits", "may_sign_release_tags",
    }
    if not isinstance(policy, dict) or set(policy) != required_policy:
        raise ValueError("commit signer policy fields are not exact")
    if not _SHA256.fullmatch(policy["fingerprint"]):
        raise ValueError("commit signer fingerprint is invalid")
    if policy["fingerprint"] != COMMIT_FINGERPRINT:
        raise ValueError("commit signer fingerprint mismatch")
    if policy["purpose"] != "ordinary commit signing":
        raise ValueError("commit signer purpose mismatch")
    if policy["trust_domain"] != "commit":
        raise ValueError("commit trust domain mismatch")
    if policy["source"] != "GitHub account SSH signing key":
        raise ValueError("commit signer source mismatch")
    if policy["independent_verification"] != "required":
        raise ValueError("independent verification must be required")
    if not _require_bool(policy["may_sign_commits"], "may_sign_commits"):
        raise ValueError("commit signer must sign commits")
    if _require_bool(policy["may_sign_release_tags"], "may_sign_release_tags"):
        raise ValueError("commit signer cannot sign release tags")


def load_signing_policy(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("unable to load signing policy") from exc
    if not isinstance(registry, dict):
        raise ValueError("signing policy must be an object")
    _validate_registry(registry)
    return registry


def validate_signer_for_artifact(fingerprint: str, artifact: str) -> None:
    policy = load_signing_policy()
    if artifact not in {"commit", "release_tag"}:
        raise ValueError("unknown signing artifact")
    if artifact == "commit":
        signer = policy["commit_signer_policy"]
        if fingerprint != signer["fingerprint"] or not signer["may_sign_commits"]:
            raise ValueError("fingerprint is not authorized for commits")
    else:
        signer = policy["keys"][0]
        if fingerprint != signer["fingerprint"] or not signer["may_sign_release_tags"]:
            raise ValueError("fingerprint is not authorized for release tags")


def verify_release_tag_signer(
    tag_name: str,
    expected_fingerprint: str | None = None,
    expected_target: str | None = None,
) -> str:
    """Verify an existing annotated tag and authorize its actual signer."""
    tag_type = subprocess.run(
        ["git", "cat-file", "-t", tag_name], text=True, capture_output=True, check=False
    )
    if tag_type.returncode != 0:
        raise ValueError("tag does not exist yet")
    if tag_type.stdout.strip() != "tag":
        raise ValueError("release tag must be an annotated tag")
    if expected_target is not None:
        target = subprocess.run(
            ["git", "rev-parse", f"{tag_name}^{{}}"], text=True, capture_output=True, check=False
        )
        if target.returncode != 0 or target.stdout.strip() != expected_target:
            raise ValueError("release tag target mismatch")
    verified = subprocess.run(
        ["git", "verify-tag", "--raw", tag_name], text=True, capture_output=True, check=False
    )
    if verified.returncode != 0:
        raise ValueError("release tag signature verification failed")
    verification_output = verified.stdout + verified.stderr
    match = re.search(r"VALIDSIG\s+([^\s]+)", verification_output)
    if match is None:
        match = re.search(r"key\s+(SHA256:[A-Za-z0-9+/=]+)", verification_output)
    if match is None:
        raise ValueError("release tag signer fingerprint is unavailable")
    actual = match.group(1)
    if expected_fingerprint is not None and actual != expected_fingerprint:
        raise ValueError("release tag signer fingerprint mismatch")
    validate_signer_for_artifact(actual, "release_tag")
    return actual

"""Fail-closed consumer for the project's separated signing trust domains."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/maintainers/release-signing-keys.json"


def load_signing_policy(path: Path = REGISTRY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise ValueError("signing registry must contain keys")
    release = [item for item in payload["keys"] if isinstance(item, dict)]
    if len(release) != 1:
        raise ValueError("signing registry must contain exactly one release key")
    commit = payload.get("commit")
    if not isinstance(commit, dict):
        raise ValueError("commit signer policy is required")
    entries = [release[0], commit]
    fingerprints = [item.get("fingerprint") for item in entries]
    domains = [item.get("trust_domain") for item in entries]
    if len(set(fingerprints)) != 2 or len(set(domains)) != 2:
        raise ValueError("signer fingerprints and trust domains must be unique")
    return {"release_tag": release[0], "commit": commit}


def validate_signer_for_artifact(
    fingerprint: str, artifact: str, *, policy: dict[str, Any] | None = None
) -> bool:
    policy = load_signing_policy() if policy is None else policy
    entry = policy.get(artifact)
    if not isinstance(entry, dict):
        raise ValueError("unknown artifact")
    if entry.get("fingerprint") != fingerprint:
        raise ValueError("unknown signer fingerprint")
    if artifact == "commit":
        required = (entry.get("format") == "ssh", entry.get("may_sign_commits") is True,
                    entry.get("may_sign_release_tags") is False,
                    entry.get("trust_domain") == "commit")
    elif artifact == "release_tag":
        required = (entry.get("format") == "openpgp", entry.get("may_sign_commits") is False,
                    entry.get("may_sign_release_tags") is True,
                    entry.get("trust_domain") == "release_tag")
    else:
        raise ValueError("unknown artifact")
    if not all(required):
        raise ValueError("signer policy conflicts with artifact trust domain")
    return True

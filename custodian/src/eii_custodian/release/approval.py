"""Shared independent-approval checks for candidates and assembly envelopes."""

from __future__ import annotations


def approval_reason(review: object, code_version: str, input_sha256: str) -> str | None:
    if type(review) is not dict or set(review) != {
        "verdict",
        "builder",
        "reviewer",
        "code_version",
        "input_sha256",
    }:
        return "approval_fields_invalid"
    if review["verdict"] != "APPROVED":
        return "approval_verdict_invalid"
    if type(review["builder"]) is not str or not review["builder"].strip():
        return "approval_builder_invalid"
    if type(review["reviewer"]) is not str or not review["reviewer"].strip():
        return "approval_reviewer_invalid"
    if review["builder"].strip().casefold() == review["reviewer"].strip().casefold():
        return "approval_same_maker"
    if review["code_version"] != code_version:
        return "approval_code_mismatch"
    if review["input_sha256"] != input_sha256:
        return "approval_hash_mismatch"
    return None

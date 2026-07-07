"""Shared identity shape returned by all social IdP providers (Google, Apple, …)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedIdentity:
    """Normalized, trusted identity claims after IdP token verification."""

    provider: str
    subject: str                 # stable unique ID from the IdP (e.g. Google's `sub`)
    email: str | None
    email_verified: bool
    given_name: str
    family_name: str
    picture_url: str | None
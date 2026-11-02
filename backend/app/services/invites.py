"""Invite-code generation and validation."""

from __future__ import annotations

import re
import secrets

# No 0/O or 1/I: codes are read aloud and typed by hand.
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_RE = re.compile(rf"^[{INVITE_ALPHABET}]{{6,12}}$")


def generate_invite_code(length: int = 8) -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))


def normalize_invite_code(value: str) -> str:
    return value.strip().upper()


def is_valid_invite_code(value: str, length: int = 8) -> bool:
    return len(value) == length and bool(_CODE_RE.fullmatch(value))

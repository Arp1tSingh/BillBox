from __future__ import annotations

import re

import pytest

from app.services.invites import (
    INVITE_ALPHABET,
    generate_invite_code,
    is_valid_invite_code,
    normalize_invite_code,
)


def test_generate_invite_code_uses_unambiguous_alphabet() -> None:
    code = generate_invite_code(8)
    assert len(code) == 8
    assert set(code) <= set(INVITE_ALPHABET)
    assert not set(code) & set("01OI")


def test_generated_codes_are_distinct() -> None:
    assert len({generate_invite_code(8) for _ in range(100)}) == 100


def test_normalize_and_validate() -> None:
    assert normalize_invite_code("  abcd2345 ") == "ABCD2345"
    assert is_valid_invite_code("ABCD2345")
    assert not is_valid_invite_code("ABCD2345X")
    assert not is_valid_invite_code("ABCD2340")
    assert not is_valid_invite_code("abcd2345")


@pytest.mark.parametrize("code", ["A" * 6, "A" * 12])
def test_length_boundaries(code: str) -> None:
    assert is_valid_invite_code(code, len(code))


def test_empty_code_is_invalid() -> None:
    assert not is_valid_invite_code("", 8)


def test_code_regex_matches_shape() -> None:
    assert re.fullmatch(r"[A-Z2-9]{8}", generate_invite_code(8))

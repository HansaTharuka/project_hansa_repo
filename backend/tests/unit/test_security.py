"""`core/security.py` — bcrypt hashing/verification and JWT issuance/decoding
(E2-S1 AC3, AC4; ut-051, ut-052).
"""

from __future__ import annotations

import time

import bcrypt
import jwt
import pytest

from src.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

TEST_SECRET = "test-secret-not-real"  # pragma: allowlist secret
KNOWN_PLAINTEXT_PASSWORD = "Correct-Horse-Battery-Staple-9"  # pragma: allowlist secret


def _token_with_exp(exp_offset_seconds: int, *, secret: str = TEST_SECRET) -> str:
    """Build a token whose `exp` claim sits `exp_offset_seconds` from real now,
    bypassing `create_access_token`'s own expiry-minutes computation so the
    expiry boundary can be tested without mocking any clock or sleeping."""
    now = int(time.time())
    payload = {"sub": "7", "role": "customer", "iat": now, "exp": now + exp_offset_seconds}
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def test_hash_password_produces_a_hash_bcrypt_checkpw_accepts() -> None:
    hashed = hash_password(KNOWN_PLAINTEXT_PASSWORD)

    assert bcrypt.checkpw(KNOWN_PLAINTEXT_PASSWORD.encode("utf-8"), hashed.encode("utf-8"))


def test_verify_password_true_for_correct_plaintext_false_for_wrong_plaintext() -> None:
    hashed = hash_password(KNOWN_PLAINTEXT_PASSWORD)

    assert verify_password(KNOWN_PLAINTEXT_PASSWORD, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_uses_bcrypt_checkpw_not_string_equality() -> None:
    # A hash for a *different* plaintext must never verify, even though string
    # equality is never how bcrypt hashes compare (each hash embeds a random salt).
    hashed_for_other_password = hash_password("some-other-password")

    assert verify_password(KNOWN_PLAINTEXT_PASSWORD, hashed_for_other_password) is False


def test_jwt_algorithm_is_hs256() -> None:
    assert JWT_ALGORITHM == "HS256"


def test_create_access_token_payload_round_trips_sub_and_role() -> None:
    token = create_access_token("42", "advisor", expiry_minutes=60, secret=TEST_SECRET)

    decoded = decode_access_token(token, secret=TEST_SECRET)

    assert decoded["sub"] == "42"
    assert decoded["role"] == "advisor"


def test_create_access_token_exp_claim_is_expiry_minutes_after_iat() -> None:
    token = create_access_token("9", "admin", expiry_minutes=15, secret=TEST_SECRET)

    decoded = decode_access_token(token, secret=TEST_SECRET)

    assert decoded["exp"] - decoded["iat"] == 15 * 60


def test_decode_access_token_accepts_a_token_still_within_its_expiry_window() -> None:
    token = _token_with_exp(60)  # still valid for another minute

    decoded = decode_access_token(token, secret=TEST_SECRET)

    assert decoded["sub"] == "7"


def test_decode_access_token_rejects_a_token_past_its_expiry() -> None:
    token = _token_with_exp(-120)  # expired two minutes ago

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, secret=TEST_SECRET)


def test_create_access_token_includes_customer_id_claim_when_given() -> None:
    token = create_access_token(
        "3", "customer", expiry_minutes=60, secret=TEST_SECRET, customer_id=17
    )

    decoded = decode_access_token(token, secret=TEST_SECRET)

    assert decoded["customer_id"] == 17


def test_create_access_token_omits_customer_id_claim_when_not_given() -> None:
    token = create_access_token("9", "admin", expiry_minutes=60, secret=TEST_SECRET)

    decoded = decode_access_token(token, secret=TEST_SECRET)

    assert "customer_id" not in decoded


def test_decode_access_token_rejects_a_token_signed_with_a_different_secret() -> None:
    token = create_access_token("1", "customer", expiry_minutes=60, secret=TEST_SECRET)

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, secret="a-different-secret-not-real")

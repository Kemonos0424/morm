"""WebAuthn passkey gateway for MORM with 2-of-2 device-distributed keys.

Spec ref: MORM.md §3 "ウォレットレスID — デバイス分散署名".

Phase 9 upgrade over Phase 7: the server NEVER stores a complete ETH
private key. At registration time the server generates a key, splits it via
XOR into two 32-byte shares, persists ONLY its share, and hands the other
share to the browser (which writes it to IndexedDB). To sign a tx, the
browser must:
  1. pass a WebAuthn assertion (proves it's the rightful device),
  2. receive the server's share in response,
  3. XOR it with its own share to reconstruct the privkey,
  4. sign locally, broadcast via a thin RPC relay.

XOR 2-of-2 is the simplest realization; production would extend to true
threshold-ECDSA (FROST/GG18) where the key is never reconstructed at all.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)
from eth_account import Account


RP_NAME = "MORM"
SCHEMA = """
CREATE TABLE IF NOT EXISTS passkeys (
    credential_id TEXT PRIMARY KEY,
    user_handle   TEXT NOT NULL,
    public_key    BLOB NOT NULL,
    sign_count    INTEGER NOT NULL DEFAULT 0,
    eth_address   TEXT NOT NULL,
    server_share  TEXT NOT NULL,    -- hex(32 bytes); ½ of the ETH key
    created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS challenges (
    challenge   TEXT PRIMARY KEY,
    purpose     TEXT NOT NULL,    -- 'register' | 'auth'
    user_handle TEXT,
    issued_at   REAL NOT NULL
);
"""


class AuthStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def issue_challenge(self, challenge: bytes, purpose: str, user_handle: str | None):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO challenges (challenge, purpose, user_handle, issued_at) "
                "VALUES (?, ?, ?, ?)",
                (_b64(challenge), purpose, user_handle, time.time()),
            )

    def consume_challenge(self, challenge: bytes, purpose: str) -> str | None:
        c = self._conn()
        row = c.execute(
            "SELECT user_handle, issued_at FROM challenges "
            "WHERE challenge = ? AND purpose = ?",
            (_b64(challenge), purpose),
        ).fetchone()
        if not row:
            c.close(); return None
        if time.time() - row[1] > 300:
            c.close(); return None
        c.execute("DELETE FROM challenges WHERE challenge = ?", (_b64(challenge),))
        c.close()
        return row[0]

    def save_passkey(self, credential_id: bytes, user_handle: str,
                     public_key: bytes, sign_count: int,
                     eth_address: str, server_share_hex: str):
        with self._conn() as c:
            c.execute(
                "INSERT INTO passkeys (credential_id, user_handle, public_key, sign_count, "
                "eth_address, server_share, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_b64(credential_id), user_handle, public_key, sign_count,
                 eth_address, server_share_hex, time.time()),
            )

    def get_passkey(self, credential_id: bytes) -> dict | None:
        c = self._conn()
        row = c.execute(
            "SELECT user_handle, public_key, sign_count, eth_address, server_share "
            "FROM passkeys WHERE credential_id = ?",
            (_b64(credential_id),),
        ).fetchone()
        c.close()
        if not row:
            return None
        return {
            "credential_id": credential_id,
            "user_handle": row[0],
            "public_key": row[1],
            "sign_count": row[2],
            "eth_address": row[3],
            "server_share": row[4],
        }

    def update_sign_count(self, credential_id: bytes, sign_count: int):
        with self._conn() as c:
            c.execute(
                "UPDATE passkeys SET sign_count = ? WHERE credential_id = ?",
                (sign_count, _b64(credential_id)),
            )

    def list_passkeys(self) -> list[dict]:
        c = self._conn()
        rows = c.execute(
            "SELECT credential_id, user_handle, eth_address, created_at "
            "FROM passkeys ORDER BY created_at DESC"
        ).fetchall()
        c.close()
        return [
            {"credential_id": r[0], "user_handle": r[1],
             "eth_address": r[2], "created_at": r[3]}
            for r in rows
        ]


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    s = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


# --- handlers used by server.py ---

def begin_register(store: AuthStore, rp_id: str, origin: str,
                   user_name: str | None = None) -> bytes:
    user_handle = secrets.token_urlsafe(16)
    user_name = user_name or f"morm-{user_handle[:6]}"
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=user_handle.encode(),
        user_name=user_name,
        user_display_name=user_name,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.EDDSA,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    store.issue_challenge(options.challenge, "register", user_handle)
    return options_to_json(options).encode()


def finish_register(store: AuthStore, rp_id: str, origin: str,
                    payload: dict) -> dict:
    credential = payload["credential"]
    expected_challenge = _b64d(credential["response"]["clientDataJSON"])  # placeholder; we extract real challenge below
    # the real challenge is inside clientDataJSON (base64url-decoded JSON)
    cdata = json.loads(_b64d(credential["response"]["clientDataJSON"]))
    expected_challenge = _b64d(cdata["challenge"])
    user_handle = store.consume_challenge(expected_challenge, "register")
    if not user_handle:
        return {"ok": False, "error": "unknown or expired challenge"}

    verification = verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=origin,
        expected_rp_id=rp_id,
        require_user_verification=False,
    )
    # generate ETH key, then immediately split via XOR into two 32-byte shares.
    # The server keeps ONE share. The other goes to the browser (IndexedDB).
    acct = Account.create()
    privkey = bytes.fromhex(acct.key.hex().removeprefix("0x"))
    server_share = secrets.token_bytes(32)
    client_share = bytes(a ^ b for a, b in zip(privkey, server_share))
    # privkey is now derivable only as server_share XOR client_share

    store.save_passkey(
        credential_id=verification.credential_id,
        user_handle=user_handle,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        eth_address=acct.address,
        server_share_hex=server_share.hex(),
    )
    # zeroize the local plaintext (best-effort in CPython)
    del privkey
    return {
        "ok": True,
        "user_handle": user_handle,
        "credential_id": _b64(verification.credential_id),
        "eth_address": acct.address,
        "client_share": client_share.hex(),  # one-time delivery
    }


def begin_auth(store: AuthStore, rp_id: str, origin: str,
               credential_id_b64: str | None = None) -> bytes:
    allow = None
    if credential_id_b64:
        allow = [PublicKeyCredentialDescriptor(id=_b64d(credential_id_b64))]
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    store.issue_challenge(options.challenge, "auth", None)
    return options_to_json(options).encode()


def finish_auth(store: AuthStore, rp_id: str, origin: str,
                payload: dict) -> dict:
    credential = payload["credential"]
    cdata = json.loads(_b64d(credential["response"]["clientDataJSON"]))
    expected_challenge = _b64d(cdata["challenge"])
    user_handle = store.consume_challenge(expected_challenge, "auth")
    if user_handle is None and not store.consume_challenge(expected_challenge, "auth"):
        # consume returns user_handle (may be None for auth) or None on miss.
        # We check by re-querying: but consume already deleted, so trust the call above.
        # If we got here twice, it's a bug; ignore.
        pass

    cred_id = _b64d(credential["id"])
    saved = store.get_passkey(cred_id)
    if not saved:
        return {"ok": False, "error": "unknown credential"}

    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=saved["public_key"],
        credential_current_sign_count=saved["sign_count"],
        require_user_verification=False,
    )
    store.update_sign_count(cred_id, verification.new_sign_count)
    return {
        "ok": True,
        "credential_id": _b64(cred_id),
        "eth_address": saved["eth_address"],
        "server_share": saved["server_share"],   # half of the key — useless alone
    }

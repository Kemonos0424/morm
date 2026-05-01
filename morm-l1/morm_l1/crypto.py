"""ed25519 wrappers — small surface so we can swap implementations later."""
from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

# MORM Chain native address: prefix + 32-char base32 of BLAKE2b-32 last 20 bytes.
# Total = 35 chars. Designed to be visually distinct from EVM 0x and Bitcoin
# addresses; survives copy-paste round-trips (no padding, lowercase only).
ADDR_PREFIX = "m0r"


def keygen() -> tuple[bytes, bytes]:
    """Return (privkey32, pubkey32). Privkey is the 32-byte seed; pubkey is the
    serialized Ed25519 public key (also 32 bytes)."""
    sk = Ed25519PrivateKey.generate()
    seed = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pk = sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return seed, pk


def pubkey_from_seed(seed: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def sign(seed: bytes, msg: bytes) -> bytes:
    return Ed25519PrivateKey.from_private_bytes(seed).sign(msg)


def verify(pubkey: bytes, sig: bytes, msg: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(pubkey).verify(sig, msg)
        return True
    except Exception:
        return False


def address(pubkey: bytes) -> str:
    """MORM Chain address: m0r + base32(BLAKE2b-32(pubkey)[-20:]).

    35-char total, lowercase. To go to EVM/bytes20 form, use `address_to_bytes20`.
    """
    raw20 = hashlib.blake2b(pubkey, digest_size=32).digest()[-20:]
    body = base64.b32encode(raw20).decode().lower().rstrip("=")
    return ADDR_PREFIX + body


def parse_address(s: str) -> bytes:
    """Accept m0r…  (native) or 0x…  (legacy/EVM bytes20) and return 20 bytes."""
    if not isinstance(s, str):
        raise ValueError(f"address must be str, got {type(s).__name__}")
    if s.startswith(ADDR_PREFIX):
        body = s[len(ADDR_PREFIX):].upper()
        pad = (-len(body)) % 8
        try:
            raw = base64.b32decode(body + "=" * pad)
        except Exception as e:
            raise ValueError(f"bad m0r address: {e}") from None
        if len(raw) != 20:
            raise ValueError(f"m0r address must decode to 20 bytes, got {len(raw)}")
        return raw
    if s.startswith("0x") and len(s) == 42:
        return bytes.fromhex(s[2:])
    # legacy synthetic addresses used by early-Phase code (e.g. "0xescrow")
    if s.startswith("0x"):
        return s.encode()      # opaque tag — not an EVM address
    raise ValueError(f"unknown address format: {s!r}")


def address_to_bytes20(addr: str) -> bytes:
    """Helper for the EVM bridge — coerce an address (any form) to 20 bytes."""
    raw = parse_address(addr)
    if len(raw) != 20:
        raise ValueError(f"cannot map {addr!r} to bytes20 (got {len(raw)} bytes)")
    return raw


def bytes20_to_address(b: bytes) -> str:
    """Inverse of address_to_bytes20 — produce an m0r address from bytes20."""
    if len(b) != 20:
        raise ValueError(f"need exactly 20 bytes, got {len(b)}")
    body = base64.b32encode(b).decode().lower().rstrip("=")
    return ADDR_PREFIX + body

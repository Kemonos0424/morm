"""Shamir Secret Sharing over GF(256) — pure Python, no deps.

Spec ref: MORM.md §3 — "ソーシャル・リカバリー: 自分の他デバイス (PC/スマホ/
ゲーム機) を組み合わせて、新しいデバイスへアカウントを復旧". A 32-byte ed25519
seed is split into N shares; any T (threshold) shares can reconstruct it,
fewer than T leak nothing about the secret.

Each byte of the secret is split independently using a degree-(T-1)
polynomial over GF(2^8) (with the AES irreducible polynomial 0x11B).
Concatenated, the per-byte y-values form one share.

Wire format: a share is `<x:1byte> || <ys:Nbytes>` where x is the share index
(1..N, never 0 — that would be the secret itself).
"""
from __future__ import annotations

import secrets
from typing import Sequence


# GF(256) tables — built once at import time.
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for i in range(255):
    _EXP[i] = _x
    _LOG[_x] = i
    _x ^= (_x << 1)
    if _x & 0x100:
        _x ^= 0x11B
for i in range(255, 512):
    _EXP[i] = _EXP[i - 255]


def _gmul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[(_LOG[a] + _LOG[b]) % 255]


def _gdiv(a: int, b: int) -> int:
    if a == 0:
        return 0
    if b == 0:
        raise ZeroDivisionError("gf256 div by zero")
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def _eval_poly(coeffs: Sequence[int], x: int) -> int:
    """Horner's method in GF(256)."""
    y = 0
    for c in reversed(coeffs):
        y = _gmul(y, x) ^ c
    return y


def split(secret: bytes, threshold: int, num_shares: int) -> list[bytes]:
    """Return `num_shares` byte-string shares; any `threshold` reconstruct."""
    if not (1 <= threshold <= num_shares <= 255):
        raise ValueError("require 1 <= threshold <= num_shares <= 255")
    if not secret:
        raise ValueError("empty secret")

    shares: list[list[int]] = [[i + 1] for i in range(num_shares)]  # x-coord byte first
    for byte in secret:
        # random degree-(threshold-1) polynomial with constant = byte
        poly = [byte] + [secrets.randbelow(256) for _ in range(threshold - 1)]
        for i in range(num_shares):
            x = i + 1
            shares[i].append(_eval_poly(poly, x))
    return [bytes(s) for s in shares]


def combine(shares: Sequence[bytes]) -> bytes:
    """Reconstruct the secret from `threshold` (or more) shares."""
    if not shares:
        raise ValueError("no shares")
    n = len(shares[0])
    for s in shares:
        if len(s) != n or n < 2:
            raise ValueError("inconsistent share length")

    xs = [s[0] for s in shares]
    if len(set(xs)) != len(xs):
        raise ValueError("duplicate share indices")

    out = bytearray()
    for byte_idx in range(1, n):
        # Lagrange interpolation at x=0
        secret_byte = 0
        for i, share_i in enumerate(shares):
            num = 1
            den = 1
            for j, share_j in enumerate(shares):
                if i == j:
                    continue
                num = _gmul(num, xs[j])               # (0 - x_j) ≡ x_j in GF(2^k)
                den = _gmul(den, xs[i] ^ xs[j])
            secret_byte ^= _gmul(share_i[byte_idx], _gdiv(num, den))
        out.append(secret_byte)
    return bytes(out)

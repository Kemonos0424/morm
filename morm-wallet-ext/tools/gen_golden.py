#!/usr/bin/env python3
"""Emit golden vectors from the MORM L1 Python source (the canonical reference).

Run from anywhere; it locates ../.. /morm-l1 relative to this file. The output
JSON is consumed by packages/wallet-core/test/golden.test.mjs, which asserts the
JS wallet-core reproduces every field byte-for-byte (address, signing_bytes,
signature). If this generator and the JS core ever disagree, the test fails —
that is the whole point of Phase 0.

Deterministic: seeds are fixed constants (NOT random), so re-running produces an
identical file and the test is stable. These seeds are test-only; never fund the
addresses they derive.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
L1 = os.path.abspath(os.path.join(HERE, "..", "..", "morm-l1"))
sys.path.insert(0, L1)

from morm_l1 import crypto  # noqa: E402
from morm_l1.tx import Transaction, TxKind  # noqa: E402

# Fixed, test-only 32-byte seeds (hex). Chosen to exercise edge bytes (0x00, 0xff).
SEEDS = [
    "00" * 32,
    "ff" * 32,
    "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20",
    "8f3c1d9e5a7b0246c8e1f0a3b5d7091133557799bbddff0022446688aaccee01",
]


def vector_for(seed_hex: str, nonce: int, amount: int):
    seed = bytes.fromhex(seed_hex)
    pub = crypto.pubkey_from_seed(seed)
    addr = crypto.address(pub)

    # A canonical TRANSFER tx (kind 6). Recipient = a distinct address derived
    # from the same seed XOR 0x5A, so the vector is self-consistent.
    recip_seed = bytes((b ^ 0x5A) for b in seed)
    to_addr = crypto.address(crypto.pubkey_from_seed(recip_seed))

    tx = Transaction.transfer(pub, nonce, to=to_addr, amount=amount)
    signing_bytes = tx.signing_bytes()
    tx.sign(seed)

    # BRIDGE_BURN (kind 21) vector — same signer/nonce, EVM recipient destination.
    evm_recipient = "0x" + (recip_seed[:20]).hex()
    bb = Transaction.bridge_burn(pub, nonce, amount=amount, evm_recipient=evm_recipient, token="MORM")
    bb_sb = bb.signing_bytes()
    bb.sign(seed)

    return {
        "seed_hex": seed_hex,
        "pubkey_hex": pub.hex(),
        "address": addr,
        "recovery_key": "morm-rk1-" + _rk_base32(seed),
        "tx": {
            "kind": int(TxKind.TRANSFER),
            "sender": pub.hex(),
            "nonce": nonce,
            # amount_str is the lossless decimal (JSON numbers >2^53 lose precision
            # when a JS test JSON.parse()s them — the JS core uses BigInt).
            "amount_str": str(amount),
            "payload": {"to": to_addr, "amount": amount},
            "signing_bytes_utf8": signing_bytes.decode("utf-8"),
            "signing_bytes_hex": signing_bytes.hex(),
            "signature_hex": tx.signature.hex(),
            "tx_hash_hex": tx.hash().hex(),
        },
        "bridge_burn": {
            "kind": int(TxKind.BRIDGE_BURN),
            "sender": pub.hex(),
            "nonce": nonce,
            "amount_str": str(amount),
            "evm_recipient": evm_recipient,
            "token": "MORM",
            "signing_bytes_utf8": bb_sb.decode("utf-8"),
            "signature_hex": bb.signature.hex(),
        },
    }


def _rk_base32(seed: bytes) -> str:
    # Mirror account.html seedToRecovery: base32(lowercase a-z2-7), 4-char groups.
    import base64
    body = base64.b32encode(seed).decode().lower().rstrip("=")
    return " ".join(body[i:i + 4] for i in range(0, len(body), 4))


# (seed_index, nonce, amount) — the last amount exceeds 2^53 to prove the JS
# BigInt path signs large balances (MORM reaches 京 = 1e16+) without precision loss.
CASES = [
    (0, 0, 1000),
    (1, 1, 2000),
    (2, 2, 3000),
    (3, 3, 12345678901234567890),
]


def main():
    vectors = []
    for seed_idx, nonce, amount in CASES:
        vectors.append(vector_for(SEEDS[seed_idx], nonce=nonce, amount=amount))
    out = {
        "note": "MORM wallet-core golden vectors. Generated from morm-l1 Python. Test-only seeds.",
        "address_prefix": crypto.ADDR_PREFIX,
        "vectors": vectors,
    }
    dest = os.path.abspath(os.path.join(HERE, "..", "packages", "wallet-core", "test", "golden.json"))
    with open(dest, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"wrote {len(vectors)} vectors -> {dest}")


if __name__ == "__main__":
    main()

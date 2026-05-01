"""MORM Chain blocks — DAG-style: each block references ≥1 parents.

The DAG ordering is what differentiates this from a linear chain. In Phase
10a we still produce one block per round (single producer), but the parent
list is multi-valued so 10b's PoUW-driven concurrent producers can be added
without changing the format.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field

from . import crypto
from .tx import Transaction


@dataclass
class BlockHeader:
    height: int
    parent_hashes: list[bytes]   # ≥1; first is the "primary" parent for naming
    producer: bytes              # 32-byte pubkey
    timestamp: int               # unix ms
    state_root: bytes            # SHA256 of canonicalized post-state
    tx_root: bytes               # SHA256 of concatenated tx hashes (sequential)

    def signing_bytes(self) -> bytes:
        body = {
            "height": self.height,
            "parents": [h.hex() for h in self.parent_hashes],
            "producer": self.producer.hex(),
            "timestamp": self.timestamp,
            "state_root": self.state_root.hex(),
            "tx_root": self.tx_root.hex(),
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()

    def hash(self) -> bytes:
        return hashlib.sha256(self.signing_bytes()).digest()


@dataclass
class Block:
    header: BlockHeader
    transactions: list[Transaction]
    signature: bytes = b""

    def hash(self) -> bytes:
        return self.header.hash()

    def sign(self, seed: bytes) -> "Block":
        self.signature = crypto.sign(seed, self.header.signing_bytes())
        return self

    def verify(self) -> bool:
        if not self.signature:
            return False
        if not crypto.verify(self.header.producer, self.signature,
                              self.header.signing_bytes()):
            return False
        # tx_root sanity
        expected = compute_tx_root(self.transactions)
        if expected != self.header.tx_root:
            return False
        return all(tx.verify() for tx in self.transactions)

    def to_dict(self) -> dict:
        return {
            "header": {
                "height": self.header.height,
                "parent_hashes": [h.hex() for h in self.header.parent_hashes],
                "producer": self.header.producer.hex(),
                "timestamp": self.header.timestamp,
                "state_root": self.header.state_root.hex(),
                "tx_root": self.header.tx_root.hex(),
            },
            "transactions": [tx.to_dict() for tx in self.transactions],
            "signature": self.signature.hex(),
            "hash": self.hash().hex(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        h = d["header"]
        hdr = BlockHeader(
            height=int(h["height"]),
            parent_hashes=[bytes.fromhex(p) for p in h["parent_hashes"]],
            producer=bytes.fromhex(h["producer"]),
            timestamp=int(h["timestamp"]),
            state_root=bytes.fromhex(h["state_root"]),
            tx_root=bytes.fromhex(h["tx_root"]),
        )
        txs = [Transaction.from_dict(t) for t in d["transactions"]]
        return cls(hdr, txs, signature=bytes.fromhex(d.get("signature", "")) or b"")


def compute_tx_root(txs: list[Transaction]) -> bytes:
    h = hashlib.sha256()
    for tx in txs:
        h.update(tx.hash())
    return h.digest() if txs else hashlib.sha256(b"").digest()

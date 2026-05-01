"""MORM Chain transactions.

Five native types — every interaction with the chain is one of these:
  REGISTER_CONTENT (cid, root_hash, generation_id)
  CREATE_ORDER     (order_id, content_id, seller, value)
  SUBMIT_PROOF     (order_id, role, proof_hash)
  FINALIZE         (order_id, valid)
  STAKE            (amount)

Compared with the EVM stand-in this is more idiomatic — there's no general
contract execution, just statically-defined state transitions, mirroring
Cosmos-SDK / Substrate-pallet style.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Any

from . import crypto


class TxKind(IntEnum):
    REGISTER_CONTENT  = 1
    CREATE_ORDER      = 2
    SUBMIT_PROOF      = 3
    FINALIZE          = 4
    STAKE             = 5
    TRANSFER          = 6    # plain balance move; replaces the /credit RPC
    VIEW_REWARD       = 7    # viewer earned VIEW_REWARD_AMOUNT for watching a cell
    POST_JOB          = 10   # PoUW: poster locks a bounty against a content_id
    CLAIM_JOB         = 11   # worker takes the job (winner-take-all per job)
    SUBMIT_WORK_PROOF = 12   # worker presents output_root → reward releases
    BRIDGE_MINT       = 20   # treasury-only: relayer minted from EVM lock event
    BRIDGE_BURN       = 21   # any account: burns balance, signals EVM unlock
    REGISTER_AI_SERVICE = 30 # treasury-only: whitelist a Generation-ID issuer
    REGISTER_PRODUCER   = 31 # treasury-only: add a block producer to the slot rotation

    # Phase 26a — Treasury multi-sig (M-of-N).
    REGISTER_TREASURY_SIGNERS = 32  # bootstrap: signed by the original
                                    # single-key treasury exactly once;
                                    # installs the signer set + threshold
                                    # and flips multi-sig "active". After
                                    # this, any treasury-only kind must be
                                    # wrapped in MULTISIG_TX.
    MULTISIG_TX               = 33  # wraps an inner treasury-only tx +
                                    # >=M signatures from distinct
                                    # registered signers, all over a
                                    # `multisig_signing_bytes()` digest
                                    # that includes the expected treasury
                                    # nonce (= replay protection).


@dataclass
class Transaction:
    kind: TxKind
    sender: bytes        # 32-byte ed25519 public key
    nonce: int
    payload: dict[str, Any]
    signature: bytes = b""

    # ---- (de)serialization --------------------------------------------------

    def signing_bytes(self) -> bytes:
        """Stable signing pre-image: kind | sender | nonce | canonical_payload."""
        body = {
            "kind": int(self.kind),
            "sender": self.sender.hex(),
            "nonce": self.nonce,
            "payload": _canonicalize(self.payload),
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()

    def hash(self) -> bytes:
        return hashlib.sha256(self.signing_bytes() + self.signature).digest()

    def sign(self, seed: bytes) -> "Transaction":
        self.signature = crypto.sign(seed, self.signing_bytes())
        return self

    def verify(self) -> bool:
        if not self.signature:
            return False
        return crypto.verify(self.sender, self.signature, self.signing_bytes())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = int(self.kind)
        d["sender"] = self.sender.hex()
        d["signature"] = self.signature.hex()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        return cls(
            kind=TxKind(d["kind"]),
            sender=bytes.fromhex(d["sender"]),
            nonce=int(d["nonce"]),
            payload=d["payload"],
            signature=bytes.fromhex(d.get("signature", "")) if d.get("signature") else b"",
        )

    # ---- factories ----------------------------------------------------------

    @classmethod
    def register_content(cls, sender: bytes, nonce: int, *,
                         content_id: str, root_hash: str,
                         generation_id: str | None = None,
                         ai_pubkey_hex: str | None = None,
                         ai_signature_hex: str | None = None):
        """If `generation_id` is set AND the chain has any whitelisted AI
        services, you must also pass `ai_pubkey_hex` + `ai_signature_hex`
        attesting to (generation_id || content_id)."""
        payload = {
            "content_id": content_id,
            "root_hash": root_hash,
            "generation_id": generation_id,
        }
        if ai_pubkey_hex:    payload["ai_pubkey"]    = ai_pubkey_hex
        if ai_signature_hex: payload["ai_signature"] = ai_signature_hex
        return cls(TxKind.REGISTER_CONTENT, sender, nonce, payload)

    @classmethod
    def create_order(cls, sender: bytes, nonce: int, *,
                     order_id: str, content_id: str, seller: str, value: int):
        return cls(
            TxKind.CREATE_ORDER, sender, nonce,
            {"order_id": order_id, "content_id": content_id,
             "seller": seller, "value": value},
        )

    @classmethod
    def submit_proof(cls, sender: bytes, nonce: int, *,
                     order_id: str, role: str, proof_hash: str):
        return cls(
            TxKind.SUBMIT_PROOF, sender, nonce,
            {"order_id": order_id, "role": role, "proof_hash": proof_hash},
        )

    @classmethod
    def finalize(cls, sender: bytes, nonce: int, *,
                 order_id: str, valid: bool):
        return cls(
            TxKind.FINALIZE, sender, nonce,
            {"order_id": order_id, "valid": bool(valid)},
        )

    @classmethod
    def stake(cls, sender: bytes, nonce: int, *, amount: int):
        return cls(TxKind.STAKE, sender, nonce, {"amount": amount})

    @classmethod
    def transfer(cls, sender: bytes, nonce: int, *, to: str, amount: int):
        return cls(TxKind.TRANSFER, sender, nonce,
                   {"to": to, "amount": int(amount)})

    @classmethod
    def view_reward(cls, sender: bytes, nonce: int, *,
                    content_id: str, cell_index: int):
        """Viewer claims a per-cell view reward. Sender is the viewer.
        Idempotency is enforced server-side by (viewer, content_id, cell_index)."""
        return cls(TxKind.VIEW_REWARD, sender, nonce,
                   {"content_id": content_id, "cell_index": int(cell_index)})

    @classmethod
    def post_job(cls, sender: bytes, nonce: int, *,
                 job_id: str, content_id: str, kind: str, reward: int):
        return cls(
            TxKind.POST_JOB, sender, nonce,
            {"job_id": job_id, "content_id": content_id,
             "kind": kind, "reward": int(reward)},
        )

    @classmethod
    def claim_job(cls, sender: bytes, nonce: int, *, job_id: str):
        return cls(TxKind.CLAIM_JOB, sender, nonce, {"job_id": job_id})

    @classmethod
    def submit_work_proof(cls, sender: bytes, nonce: int, *,
                           job_id: str, output_root: str):
        return cls(
            TxKind.SUBMIT_WORK_PROOF, sender, nonce,
            {"job_id": job_id, "output_root": output_root},
        )

    @classmethod
    def bridge_mint(cls, sender: bytes, nonce: int, *,
                    to: str, amount: int, evm_lock_id: str,
                    token: str = "MORM", token_address: str | None = None):
        """Treasury-signed: credits `to` with `amount` of `token` after observing
        a Locked event on the EVM bridge. token='MORM' for native ETH-bridged
        balance (capped by treasury), else 'USDC' etc. for ERC-20 mirror."""
        payload = {"to": to, "amount": int(amount), "evm_lock_id": evm_lock_id,
                   "token": token}
        if token_address:
            payload["token_address"] = token_address
        return cls(TxKind.BRIDGE_MINT, sender, nonce, payload)

    @classmethod
    def bridge_burn(cls, sender: bytes, nonce: int, *,
                    amount: int, evm_recipient: str,
                    token: str = "MORM", token_address: str | None = None):
        """Burn own balance, declare EVM destination + token kind."""
        payload = {"amount": int(amount), "evm_recipient": evm_recipient,
                   "token": token}
        if token_address:
            payload["token_address"] = token_address
        return cls(TxKind.BRIDGE_BURN, sender, nonce, payload)

    @classmethod
    def register_ai_service(cls, sender: bytes, nonce: int, *,
                            ai_pubkey_hex: str, name: str):
        return cls(
            TxKind.REGISTER_AI_SERVICE, sender, nonce,
            {"ai_pubkey": ai_pubkey_hex, "name": name},
        )

    @classmethod
    def register_producer(cls, sender: bytes, nonce: int, *,
                          producer_pubkey_hex: str, name: str):
        return cls(
            TxKind.REGISTER_PRODUCER, sender, nonce,
            {"producer_pubkey": producer_pubkey_hex, "name": name},
        )

    # ---- Phase 26a — Treasury multi-sig --------------------------------

    @classmethod
    def register_treasury_signers(cls, sender: bytes, nonce: int, *,
                                  signers: list[dict], threshold: int):
        """Bootstrap multi-sig. `sender` MUST be the original single-key
        treasury (state.py enforces this). After successful execution:
        - the signer set is recorded
        - the threshold is recorded
        - multi-sig becomes active
        - subsequent treasury-only kinds (BRIDGE_MINT / FINALIZE /
          REGISTER_AI_SERVICE / REGISTER_PRODUCER) must use MULTISIG_TX.

        `signers` is a list of {"pubkey": <64-hex>, "name": <str>}."""
        return cls(
            TxKind.REGISTER_TREASURY_SIGNERS, sender, nonce,
            {"signers": signers, "threshold": int(threshold)},
        )

    @classmethod
    def multisig_tx(cls, sender: bytes, nonce: int, *,
                    inner_kind: int, inner_payload: dict,
                    treasury_nonce: int,
                    signatures: list[dict]):
        """Multi-sig wrapper around an inner treasury-only tx.

        - `sender`/`nonce`: any registered signer (state.py validates
          membership). The submitter pays the network cost / consumes
          their own account nonce; the inner tx executes against the
          treasury account whose `accounts.nonce` advances by 1.
        - `inner_kind`: TxKind enum value of the inner tx (e.g. 20 for
          BRIDGE_MINT, 31 for REGISTER_PRODUCER).
        - `inner_payload`: the payload that would be sent on a regular
          single-key inner tx.
        - `treasury_nonce`: the **expected** treasury account nonce at
          execution time. State.py rejects if mismatch — this is the
          anti-replay binder.
        - `signatures`: list of {"pubkey": <64-hex>, "sig": <128-hex>},
          each over `multisig_signing_bytes(inner_kind, inner_payload,
          treasury_addr, treasury_nonce)`. State.py requires:
            - count ≥ threshold
            - each pubkey in registered signer set
            - all pubkeys distinct (no double-counting)
        """
        return cls(
            TxKind.MULTISIG_TX, sender, nonce,
            {
                "inner_kind": int(inner_kind),
                "inner_payload": inner_payload,
                "treasury_nonce": int(treasury_nonce),
                "signatures": signatures,
            },
        )

    @staticmethod
    def multisig_signing_bytes(inner_kind: int, inner_payload: dict,
                                treasury_addr: str, treasury_nonce: int) -> bytes:
        """Stable signing pre-image for multi-sig cosigners. Includes
        treasury_nonce so a replayed (kind, payload) pair fails on the
        next round — each multi-sig invocation requires fresh sigs."""
        body = {
            "inner_kind": int(inner_kind),
            "inner_payload": _canonicalize(inner_payload),
            "treasury_addr": treasury_addr,
            "treasury_nonce": int(treasury_nonce),
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def _canonicalize(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _canonicalize(v) for k, v in sorted(o.items())}
    if isinstance(o, (list, tuple)):
        return [_canonicalize(v) for v in o]
    if isinstance(o, bytes):
        return o.hex()
    return o

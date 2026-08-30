"""MORM export-bridge relayer — hardened, threshold-signed.

Bridges L1 MORM <-> Base wMORM via the MORMExportBridge (M-of-N multisig mint).
Replaces the single-trusted-key PoC (relayer.py) for the wMORM direction.

Forward  (L1 -> EVM):  watch L1 BRIDGE_BURN rows tagged token=EXPORT_TOKEN.
    N independent signers each RE-VERIFY the burn against the L1 ledger and
    sign mintDigest(recipient, amount, burnId). A submitter aggregates
    >= THRESHOLD signatures (ascending by signer address) and calls
    bridge.mintFromBurn(). Idempotent via on-chain minted[burnId].

Reverse  (EVM -> L1):  watch MORMExportBridge.Exit events, wait EVM_CONFIRMS
    blocks, then submit L1 BRIDGE_MINT(token=MORM) crediting the mormAddress.
    Idempotent via evm_lock_id in the L1 bridge_mints table.

Production hardening carried over from the contract review:
  - each signer's key should live on a SEPARATE host / HSM; here they are
    read from env for the testnet bring-up but the verify-before-sign gate is
    real (every signer re-reads the L1 burn before signing).
  - confirmation depth on both sides (L1 only_pending = finalized; EVM K blocks).
  - all amounts/addresses are bound into the signed digest, so a compromised
    submitter cannot redirect or inflate a mint.

Env:
  EVM_RPC, MORM_RPC, BRIDGE_ADDR, CHAIN_ID, EVM_CONFIRMS,
  SIGNER_PKS (comma-separated), THRESHOLD, SUBMITTER_PK,
  TREASURY_SEED_HEX, EXPORT_TOKEN (default "wMORM"), POLL_INTERVAL,
  START_BLOCK (optional).
Run:  python export_relayer.py            # service loop
      python export_relayer.py selftest   # digest/signature parity vs chain
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from web3 import Web3
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.messages import encode_defunct

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))

# morm_l1 (needs `cryptography`) is only required for the reverse path
# (crediting MORM on L1). selftest and the forward mint path don't need it,
# so import lazily to keep those runnable in a minimal env.
def _l1():
    from morm_l1 import crypto
    from morm_l1.tx import Transaction
    return crypto, Transaction

# ── config ────────────────────────────────────────────────────────────────
EVM_RPC      = os.environ.get("EVM_RPC", "http://127.0.0.1:8545")
MORM_RPC     = os.environ.get("MORM_RPC", "http://127.0.0.1:8900")
BRIDGE_ADDR  = os.environ.get("BRIDGE_ADDR", "")
CHAIN_ID     = int(os.environ.get("CHAIN_ID", "84532"))          # Base Sepolia
EVM_CONFIRMS = int(os.environ.get("EVM_CONFIRMS", "3"))
# eth_getLogs の1回あたり最大ブロック範囲。無料枠RPC(例: Alchemy Free=10)の制限に合わせる。
# reverse(Exit)スキャンはこの幅でチャンク化して呼ぶ→広い範囲/長期ダウン後のギャップでも失敗しない。
EVM_LOG_CHUNK = int(os.environ.get("EVM_LOG_CHUNK", "10"))
THRESHOLD    = int(os.environ.get("THRESHOLD", "2"))
EXPORT_TOKEN = os.environ.get("EXPORT_TOKEN", "MORM")   # L1 burns of this token → wMORM mint
# L1 MORM is integer (1 MORM = 1 unit); wMORM is 18-decimals. 1 L1 MORM = 1e18 wMORM-wei.
L1_MORM_SCALE = int(float(os.environ.get("L1_MORM_SCALE", str(10**18))))

# ── crash/restart-safe reverse-exit cursor ────────────────────────────────
# GAP: last_block はプロセス内でしか進まず、再起動で START_BLOCK/現在headに戻るため
# 停止中に出た Exit を取りこぼしていた。cursor をファイル永続化し、再起動で確実に再開する。
# 再スキャンは L1 側 evm_lock_id（BRIDGE_MINT の PRIMARY KEY）で冪等なので二重クレジットしない。
STATE_FILE = os.environ.get(
    "EXPORT_STATE_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".export_relayer_state.json"))
REORG_BUFFER = int(os.environ.get("EVM_REORG_BUFFER", "5"))   # 再開時に少し手前から再スキャン
DUST_FILE = os.environ.get(
    "EXPORT_DUST_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".export_relayer_dust.jsonl"))

def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(patch):
    try:
        st = _load_state(); st.update(patch)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, STATE_FILE)   # atomic
    except Exception as e:
        print(f"[export] state save failed: {e}")

def _append_dust(evm_id, morm_addr, wamount_wei, credited_morm):
    # wMORM は焼却済みだが端数/1MORM未満で満額クレジットできなかった記録（手動レビュー用）。
    try:
        with open(DUST_FILE, "a") as f:
            f.write(json.dumps({"evm_id": evm_id, "morm_addr": morm_addr,
                                "wamount_wei": str(wamount_wei), "credited_morm": credited_morm}) + "\n")
    except Exception as e:
        print(f"[export] dust log failed: {e}")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "3.0"))
MINT_PURPOSE  = "MORMExportBridge:mint"
# When the L1 treasury multisig is active (REGISTER_TREASURY_SIGNERS), the reverse
# BRIDGE_MINT is a treasury-only kind and must be wrapped in a MULTISIG_TX cosigned
# by >= threshold registered treasury signers (Ed25519 L1 keys — DISTINCT from the
# EVM SIGNER_PKS). Set TREASURY_SIGNER_SEEDS to enable the multisig reverse path;
# leave it unset to keep the legacy single-key treasury path.
TREASURY_SIGNER_SEEDS = [s.strip() for s in os.environ.get("TREASURY_SIGNER_SEEDS", "").split(",") if s.strip()]
TREASURY_MS_THRESHOLD = int(os.environ.get("TREASURY_MS_THRESHOLD", "2"))
BRIDGE_MINT_KIND = 20

# ── USDm lock/unlock (escrow) bridge — ADDITIVE mirror path ────────────────
# USDm is a USDC-backed 1:1 wrapper already on Base, so its bridge ESCROWS
# (never mints) the token: Base lock → L1 credit (account_tokens[USDm]),
# L1 burn(token=USDm) → threshold-signed unlock() releases escrow. Reuses the
# same EVM signer set (3-of-5) + treasury credit path as wMORM — only the
# unlock digest purpose differs. Leave USDM_BRIDGE_ADDR unset to disable every
# USDm path entirely (existing wMORM forward/exit stay byte-for-byte unchanged).
USDM_BRIDGE_ADDR    = os.environ.get("USDM_BRIDGE_ADDR", "")   # unset ⇒ USDm disabled
USDM_ADDR           = os.environ.get("USDM_ADDR", "")          # USDm ERC-20 (L1 token_address mirror)
USDM_TOKEN          = os.environ.get("USDM_TOKEN", "USDm")     # L1 mirror symbol
USDM_UNLOCK_PURPOSE = "USDmLockBridge:unlock"
# USDm is 6-dec on Base and mirrored 1:1 in base units on L1 (no scaling ⇒
# exact value, no dust). START cursor for the Locked scan is separate from the
# wMORM Exit cursor so the two directions never interfere.

def _keys(env: str) -> list[str]:
    return [k.strip() for k in os.environ.get(env, "").split(",") if k.strip()]


def get_morm(p):
    return json.loads(urllib.request.urlopen(MORM_RPC + p, timeout=8).read())


def post_morm(p, b):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        MORM_RPC + p, method="POST", data=json.dumps(b).encode(),
        headers={"Content-Type": "application/json"}), timeout=8).read())


class Signer:
    """One bridge signer. Re-verifies a burn against L1 before signing it."""
    def __init__(self, pk: str):
        self.acct = Account.from_key(pk)
        self.address = self.acct.address

    def verify_and_sign(self, bridge_addr, recipient, wmorm_amount, l1_amount,
                        burn_id_bytes, burn_row) -> bytes | None:
        # independent verification: the burn the submitter handed us must match
        # what the L1 ledger actually recorded (recipient + L1 amount + token).
        # The signed digest binds the SCALED wMORM amount that will be minted.
        if (Web3.to_checksum_address(burn_row["evm_recipient"]) != recipient
                or int(burn_row["amount"]) != l1_amount
                or (burn_row.get("token") or "MORM") != EXPORT_TOKEN):
            return None
        digest = mint_digest(bridge_addr, recipient, wmorm_amount, burn_id_bytes)
        sig = self.acct.sign_message(encode_defunct(primitive=digest)).signature
        return bytes(sig)

    def verify_and_sign_usdm_unlock(self, bridge_addr, recipient, amount,
                                    burn_id_bytes, burn_row) -> bytes | None:
        """USDm escrow release: re-verify the L1 burn (recipient + amount +
        token=USDm) before signing the unlock digest. USDm is mirrored 1:1 in
        base units, so the signed amount equals the L1 burn amount exactly."""
        if (Web3.to_checksum_address(burn_row["evm_recipient"]) != recipient
                or int(burn_row["amount"]) != amount
                or (burn_row.get("token") or "") != USDM_TOKEN):
            return None
        digest = unlock_digest(bridge_addr, recipient, amount, burn_id_bytes)
        sig = self.acct.sign_message(encode_defunct(primitive=digest)).signature
        return bytes(sig)


def mint_digest(bridge_addr, recipient, amount, burn_id_bytes) -> bytes:
    """Must byte-match MORMExportBridge.mintDigest()."""
    return Web3.keccak(abi_encode(
        ["address", "uint256", "string", "address", "uint256", "bytes32"],
        [Web3.to_checksum_address(bridge_addr), CHAIN_ID, MINT_PURPOSE,
         recipient, amount, burn_id_bytes]))


def unlock_digest(bridge_addr, recipient, amount, burn_id_bytes) -> bytes:
    """Must byte-match USDmLockBridge.unlockDigest():
    keccak(abi.encode(address(this), block.chainid, "USDmLockBridge:unlock",
    recipient, amount, l1BurnId))."""
    return Web3.keccak(abi_encode(
        ["address", "uint256", "string", "address", "uint256", "bytes32"],
        [Web3.to_checksum_address(bridge_addr), CHAIN_ID, USDM_UNLOCK_PURPOSE,
         recipient, amount, burn_id_bytes]))


def order_sigs(signers: list[Signer], sigs: dict[str, bytes]) -> list[bytes]:
    """Return signatures ordered by signer address ascending (contract requires
    strictly ascending for its dedup)."""
    addrs = sorted(sigs.keys(), key=lambda a: int(a, 16))
    return [sigs[a] for a in addrs]


class ExportRelayer:
    def __init__(self):
        if not BRIDGE_ADDR:
            raise SystemExit("BRIDGE_ADDR required")
        self.w3 = Web3(Web3.HTTPProvider(EVM_RPC))
        if not self.w3.is_connected():
            raise SystemExit(f"EVM RPC unreachable: {EVM_RPC}")
        self.bridge_addr = Web3.to_checksum_address(BRIDGE_ADDR)
        art = json.loads((ROOT / "morm-chain" / "out" /
                          "MORMExportBridge.sol" / "MORMExportBridge.json").read_text())
        self.bridge = self.w3.eth.contract(address=self.bridge_addr, abi=art["abi"])

        self.signers = [Signer(pk) for pk in _keys("SIGNER_PKS")]
        if len(self.signers) < THRESHOLD:
            raise SystemExit(f"need >= {THRESHOLD} SIGNER_PKS, got {len(self.signers)}")
        self.submitter = Account.from_key(os.environ["SUBMITTER_PK"])

        seed_hex = os.environ.get("TREASURY_SEED_HEX", "")
        self.treasury_seed = bytes.fromhex(seed_hex.removeprefix("0x")) if seed_hex else None
        self.treasury_signer_seeds = [bytes.fromhex(s.removeprefix("0x")) for s in TREASURY_SIGNER_SEEDS]
        if self.treasury_signer_seeds and len(self.treasury_signer_seeds) < TREASURY_MS_THRESHOLD:
            raise SystemExit(f"need >= {TREASURY_MS_THRESHOLD} TREASURY_SIGNER_SEEDS, got {len(self.treasury_signer_seeds)}")
        self.treasury_pub = None
        self.treasury_addr = os.environ.get("TREASURY_ADDRESS") or None
        if self.treasury_seed:
            crypto, _ = _l1()
            self.treasury_pub = crypto.pubkey_from_seed(self.treasury_seed)
            self.treasury_addr = crypto.address(self.treasury_pub)
        if self.treasury_signer_seeds:
            print(f"[export] reverse=MULTISIG ({len(self.treasury_signer_seeds)} signers, "
                  f"threshold {TREASURY_MS_THRESHOLD}) treasury={self.treasury_addr}")

        _st = _load_state()
        if _st.get("last_block") is not None:
            self.last_block = max(0, int(_st["last_block"]) - REORG_BUFFER)
            print(f"[export] resume last_block={self.last_block} (state -{REORG_BUFFER} reorg buffer)")
        else:
            self.last_block = int(os.environ.get("START_BLOCK", str(self.w3.eth.block_number)))
        self.handled_exits: set[str] = set()
        self.handled_burns: set[str] = set()
        for row in get_morm("/bridge/burns").get("burns", []):
            if row.get("evm_unlocked"):
                self.handled_burns.add(row["burn_tx_hash"])

        # ── USDm escrow bridge (additive; disabled unless USDM_BRIDGE_ADDR set) ──
        self.usdm_bridge = None
        if USDM_BRIDGE_ADDR:
            self.usdm_bridge_addr = Web3.to_checksum_address(USDM_BRIDGE_ADDR)
            uart = json.loads((ROOT / "morm-chain" / "out" /
                               "USDmLockBridge.sol" / "USDmLockBridge.json").read_text())
            self.usdm_bridge = self.w3.eth.contract(address=self.usdm_bridge_addr, abi=uart["abi"])
            _u = _load_state()
            if _u.get("usdm_last_block") is not None:
                self.usdm_last_block = max(0, int(_u["usdm_last_block"]) - REORG_BUFFER)
                print(f"[export] USDm resume usdm_last_block={self.usdm_last_block} "
                      f"(state -{REORG_BUFFER} reorg buffer)")
            else:
                self.usdm_last_block = int(os.environ.get("USDM_START_BLOCK",
                                                          str(self.w3.eth.block_number)))
            self.handled_locks: set[str] = set()
            self.handled_usdm_burns: set[str] = set()
            for row in get_morm("/bridge/burns").get("burns", []):
                if (row.get("token") or "") == USDM_TOKEN and row.get("evm_unlocked"):
                    self.handled_usdm_burns.add(row["burn_tx_hash"])
            print(f"[export] USDm mirror ENABLED bridge={self.usdm_bridge_addr} "
                  f"token={USDM_TOKEN} token_address={USDM_ADDR or '(none)'}")

    # ── forward: L1 burn -> EVM mint wMORM ────────────────────────────────
    def poll_l1_burns(self):
        burns = get_morm("/bridge/burns?only_pending=1").get("burns", [])
        for b in burns:
            h = b["burn_tx_hash"]
            if h in self.handled_burns or (b.get("token") or "MORM") != EXPORT_TOKEN:
                continue
            recipient = Web3.to_checksum_address(b["evm_recipient"])
            l1_amount = int(b["amount"])                 # integer MORM on L1
            amount = l1_amount * L1_MORM_SCALE            # wMORM-wei to mint (18dec)
            burn_id = bytes.fromhex(h)
            # already minted on-chain? treat as done (crash-recovery / idempotency)
            if self.bridge.functions.minted(burn_id).call():
                self._confirm_burn(h)
                continue
            # gather signatures from independent signers (verify-before-sign)
            sigs: dict[str, bytes] = {}
            for s in self.signers:
                sig = s.verify_and_sign(self.bridge_addr, recipient, amount, l1_amount, burn_id, b)
                if sig:
                    sigs[s.address] = sig
                if len(sigs) >= THRESHOLD:
                    break
            if len(sigs) < THRESHOLD:
                print(f"[export] burn {h[:16]}… insufficient valid signers "
                      f"({len(sigs)}/{THRESHOLD}) — skipping")
                continue
            ordered = order_sigs(self.signers, sigs)
            print(f"[export] L1 burn → mint {l1_amount} MORM ({amount} wMORM-wei) to {recipient} "
                  f"(burnId={h[:16]}…, {len(ordered)} sigs)")
            try:
                self._send(self.bridge.functions.mintFromBurn(
                    recipient, amount, burn_id, ordered))
                self._confirm_burn(h)
            except Exception as e:
                print(f"[export]   mint failed: {e}")

    def _confirm_burn(self, h):
        try:
            post_morm("/bridge/burn-confirmed", {"burn_tx_hash": h})
        except Exception:
            pass
        self.handled_burns.add(h)

    # ── reverse: EVM Exit -> L1 mint MORM ─────────────────────────────────
    def poll_evm_exits(self):
        head = self.w3.eth.block_number
        safe = head - EVM_CONFIRMS            # confirmation depth
        if safe < self.last_block:
            return
        crypto, Transaction = _l1()
        events = []
        _frm = self.last_block
        while _frm <= safe:                       # ≤EVM_LOG_CHUNK blocks/getLogs (free-tier RPC caps range)
            _to = min(_frm + EVM_LOG_CHUNK - 1, safe)
            events += self.bridge.events.Exit().get_logs(from_block=_frm, to_block=_to)
            _frm = _to + 1
        for ev in events:
            evm_id = f"exit:{ev.transactionHash.hex()}:{ev.logIndex}"
            if evm_id in self.handled_exits:
                continue
            if not self.treasury_addr or not (self.treasury_seed or self.treasury_signer_seeds):
                print("[export] no treasury credentials — cannot credit L1, skipping exit")
                continue
            morm_addr = crypto.bytes20_to_address(bytes(ev.args["mormAddress"]))
            wamount = int(ev.args["amount"])          # wMORM-wei burned on Base
            l1_amount = wamount // L1_MORM_SCALE       # integer MORM to credit on L1
            remainder = wamount % L1_MORM_SCALE
            if l1_amount <= 0:
                # wMORMは焼却済みだが1MORM未満＝整数MORMをクレジットできない。無言で失わせず、
                # 手動レビュー用に記録して大声で警告する。根本対策はコントラクトの MIN_EXIT>=1e18。
                print(f"[export][ALERT] exit {evm_id[:26]}… below 1 MORM ({wamount} wei) — NOT creditable; "
                      f"wMORM burned. Set MIN_EXIT>=1e18 on the bridge to prevent this.")
                _append_dust(evm_id, morm_addr, wamount, 0)
                self.handled_exits.add(evm_id)
                continue
            if remainder:
                # 端数(1MORM未満の余り)はfloorで失われる。満額分はクレジットしつつ記録+警告。
                print(f"[export][ALERT] exit {evm_id[:26]}… has {remainder} wei fractional remainder — "
                      f"lost (credited {l1_amount} MORM). Enforce whole-MORM exits (MIN_EXIT / step).")
                _append_dust(evm_id, morm_addr, wamount, l1_amount)
            print(f"[export] EVM Exit → credit {l1_amount} MORM to {morm_addr} "
                  f"(evm_id={evm_id[:26]}…)")
            try:
                self._credit_l1(morm_addr, l1_amount, evm_id)
                self.handled_exits.add(evm_id)
            except Exception as e:
                print(f"[export]   credit failed: {e}")
        self.last_block = safe + 1
        _save_state({"last_block": self.last_block})

    def _credit_l1(self, morm_addr, l1_amount, evm_id, token="MORM", token_address=None):
        """Reverse L1 credit (BRIDGE_MINT). Uses the treasury multisig
        (MULTISIG_TX cosigned by >= threshold registered signers) when
        TREASURY_SIGNER_SEEDS is configured; else the legacy single-key path.
        BRIDGE_MINT's evm_lock_id makes this idempotent on the L1 side.
        token/token_address default to native MORM (wMORM exit path unchanged);
        for the USDm mirror pass token='USDm', token_address=USDM_ADDR ⇒ a pure
        account_tokens mirror with no treasury balance draw."""
        crypto, Transaction = _l1()
        inner_payload = {"to": morm_addr, "amount": int(l1_amount),
                         "evm_lock_id": evm_id, "token": token}
        if token_address:
            inner_payload["token_address"] = token_address
        if self.treasury_signer_seeds:
            # M-of-N: cosign multisig_signing_bytes bound to the treasury nonce,
            # then submit the MULTISIG_TX as one of the registered signers.
            treasury_nonce = get_morm(f"/account/{self.treasury_addr}")["nonce"]
            msg = Transaction.multisig_signing_bytes(
                BRIDGE_MINT_KIND, inner_payload, self.treasury_addr, treasury_nonce)
            sigs = [{"pubkey": crypto.pubkey_from_seed(s).hex(),
                     "sig": crypto.sign(s, msg).hex()} for s in self.treasury_signer_seeds]
            sub_seed = self.treasury_signer_seeds[0]
            sub_pub = crypto.pubkey_from_seed(sub_seed)
            sub_addr = crypto.address(sub_pub)
            sub_nonce = get_morm(f"/account/{sub_addr}")["nonce"]
            tx = Transaction.multisig_tx(
                sub_pub, sub_nonce, inner_kind=BRIDGE_MINT_KIND,
                inner_payload=inner_payload, treasury_nonce=treasury_nonce,
                signatures=sigs).sign(sub_seed)
            return post_morm("/tx", tx.to_dict())
        # legacy single-key treasury
        nonce = get_morm(f"/account/{self.treasury_addr}")["nonce"]
        tx = Transaction.bridge_mint(
            self.treasury_pub, nonce, to=morm_addr, amount=int(l1_amount),
            evm_lock_id=evm_id, token=token, token_address=token_address,
        ).sign(self.treasury_seed)
        return post_morm("/tx", tx.to_dict())

    # ── USDm forward: Base Locked -> L1 credit account_tokens[USDm] ─────────
    def poll_evm_locks(self):
        if not self.usdm_bridge:
            return
        head = self.w3.eth.block_number
        safe = head - EVM_CONFIRMS
        if safe < self.usdm_last_block:
            return
        crypto, _ = _l1()
        events = []
        _frm = self.usdm_last_block
        while _frm <= safe:                       # ≤EVM_LOG_CHUNK blocks/getLogs (free-tier cap)
            _to = min(_frm + EVM_LOG_CHUNK - 1, safe)
            events += self.usdm_bridge.events.Locked().get_logs(from_block=_frm, to_block=_to)
            _frm = _to + 1
        for ev in events:
            evm_id = f"usdmlock:{ev.transactionHash.hex()}:{ev.logIndex}"
            if evm_id in self.handled_locks:
                continue
            if not self.treasury_addr or not (self.treasury_seed or self.treasury_signer_seeds):
                print("[export] no treasury credentials — cannot credit USDm, skipping lock")
                continue
            morm_addr = crypto.bytes20_to_address(bytes(ev.args["mormAddress"]))
            amount = int(ev.args["amount"])       # USDm base units (6dec) — mirrored 1:1
            if amount <= 0:
                self.handled_locks.add(evm_id)
                continue
            print(f"[export] USDm Lock → credit {amount} {USDM_TOKEN}-units to {morm_addr} "
                  f"(evm_id={evm_id[:30]}…)")
            try:
                self._credit_l1(morm_addr, amount, evm_id,
                                token=USDM_TOKEN, token_address=(USDM_ADDR or None))
                self.handled_locks.add(evm_id)
            except Exception as e:
                print(f"[export]   USDm credit failed: {e}")
        self.usdm_last_block = safe + 1
        _save_state({"usdm_last_block": self.usdm_last_block})

    # ── USDm reverse: L1 burn(token=USDm) -> Base unlock() releases escrow ──
    def poll_l1_usdm_burns(self):
        if not self.usdm_bridge:
            return
        burns = get_morm("/bridge/burns?only_pending=1").get("burns", [])
        for b in burns:
            h = b["burn_tx_hash"]
            if h in self.handled_usdm_burns or (b.get("token") or "") != USDM_TOKEN:
                continue
            recipient = Web3.to_checksum_address(b["evm_recipient"])
            amount = int(b["amount"])             # USDm base units, released 1:1
            burn_id = bytes.fromhex(h)
            # already released on-chain? (crash-recovery / idempotency)
            if self.usdm_bridge.functions.unlockedBurn(burn_id).call():
                self._confirm_usdm_burn(h)
                continue
            sigs: dict[str, bytes] = {}
            for s in self.signers:
                sig = s.verify_and_sign_usdm_unlock(self.usdm_bridge_addr, recipient,
                                                    amount, burn_id, b)
                if sig:
                    sigs[s.address] = sig
                if len(sigs) >= THRESHOLD:
                    break
            if len(sigs) < THRESHOLD:
                print(f"[export] usdm burn {h[:16]}… insufficient valid signers "
                      f"({len(sigs)}/{THRESHOLD}) — skipping")
                continue
            ordered = order_sigs(self.signers, sigs)
            print(f"[export] L1 USDm burn → unlock {amount} {USDM_TOKEN}-units to {recipient} "
                  f"(burnId={h[:16]}…, {len(ordered)} sigs)")
            try:
                self._send(self.usdm_bridge.functions.unlock(recipient, amount, burn_id, ordered))
                self._confirm_usdm_burn(h)
            except Exception as e:
                print(f"[export]   usdm unlock failed: {e}")

    def _confirm_usdm_burn(self, h):
        try:
            post_morm("/bridge/burn-confirmed", {"burn_tx_hash": h})
        except Exception:
            pass
        self.handled_usdm_burns.add(h)

    def _send(self, fn):
        built = fn.build_transaction({
            "from": self.submitter.address,
            "nonce": self.w3.eth.get_transaction_count(self.submitter.address),
            "gas": 400_000,
            "gasPrice": self.w3.eth.gas_price * 2,   # legacy tx (robust on Base L2)
            "chainId": CHAIN_ID,
        })
        signed = self.submitter.sign_transaction(built)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        r = self.w3.eth.wait_for_transaction_receipt(h, timeout=60)
        if r.status != 1:
            raise RuntimeError(f"tx reverted: {h.hex()}")
        print(f"[export]   ok evm_tx={h.hex()[:18]}…")

    def run(self):
        print(f"[export] running. evm={EVM_RPC} morm={MORM_RPC} bridge={self.bridge_addr}")
        print(f"         signers={[s.address for s in self.signers]} threshold={THRESHOLD}")
        while True:
            try:
                self.poll_l1_burns()
                self.poll_evm_exits()
                self.poll_l1_usdm_burns()   # no-op unless USDM_BRIDGE_ADDR set
                self.poll_evm_locks()       # no-op unless USDM_BRIDGE_ADDR set
            except Exception as e:
                print(f"[export] poll error: {e}")
            time.sleep(POLL_INTERVAL)


def selftest():
    """Verify our locally-computed mint digest byte-matches the deployed
    contract's mintDigest() — proves the relayer signs exactly what the
    contract verifies."""
    if not BRIDGE_ADDR:
        raise SystemExit("BRIDGE_ADDR required for selftest")
    w3 = Web3(Web3.HTTPProvider(EVM_RPC))
    art = json.loads((ROOT / "morm-chain" / "out" /
                      "MORMExportBridge.sol" / "MORMExportBridge.json").read_text())
    bridge = w3.eth.contract(address=Web3.to_checksum_address(BRIDGE_ADDR), abi=art["abi"])
    recipient = Web3.to_checksum_address("0x000000000000000000000000000000000000bEEF")
    amount = 100 * 10**18
    burn_id = Web3.keccak(text="selftest-burn")
    onchain = bridge.functions.mintDigest(recipient, amount, burn_id).call()
    local = mint_digest(BRIDGE_ADDR, recipient, amount, burn_id)
    ok = bytes(onchain) == bytes(local)
    print("[wMORM mint] on-chain:", Web3.to_hex(onchain))
    print("[wMORM mint] local   :", Web3.to_hex(local))
    print("[wMORM mint]", "MATCH" if ok else "MISMATCH")

    # USDm unlock digest parity (only if the escrow bridge is configured)
    if USDM_BRIDGE_ADDR:
        uart = json.loads((ROOT / "morm-chain" / "out" /
                           "USDmLockBridge.sol" / "USDmLockBridge.json").read_text())
        ub = w3.eth.contract(address=Web3.to_checksum_address(USDM_BRIDGE_ADDR), abi=uart["abi"])
        u_amount = 1_000_000                       # 1 USDm (6dec)
        u_burn = Web3.keccak(text="selftest-usdm-unlock")
        u_onchain = ub.functions.unlockDigest(recipient, u_amount, u_burn).call()
        u_local = unlock_digest(USDM_BRIDGE_ADDR, recipient, u_amount, u_burn)
        u_ok = bytes(u_onchain) == bytes(u_local)
        print("[USDm unlock] on-chain:", Web3.to_hex(u_onchain))
        print("[USDm unlock] local   :", Web3.to_hex(u_local))
        print("[USDm unlock]", "MATCH" if u_ok else "MISMATCH")
        ok = ok and u_ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "selftest":
        selftest()
    elif cmd == "once":                    # single forward+reverse sweep (test/cron)
        r = ExportRelayer()
        r.poll_l1_burns()
        r.poll_evm_exits()
        r.poll_l1_usdm_burns()   # no-op unless USDM_BRIDGE_ADDR set
        r.poll_evm_locks()       # no-op unless USDM_BRIDGE_ADDR set
        print("[export] once: done")
    else:
        ExportRelayer().run()

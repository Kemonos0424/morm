"""MORM bridge relayer.

Polls both sides:
  EVM (anvil) MORMBridge.Locked   → submit BRIDGE_MINT on MORM L1
  MORM L1     bridge_burns table  → call MORMBridge.unlock() on EVM, then
                                    POST /bridge/burn-confirmed back to L1

Run alongside an Anvil instance + a MORM L1 node. Single trusted relayer
in the PoC; production would run this on a quorum of validators with
threshold signatures.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "morm-l1"))

from morm_l1 import crypto                       # noqa: E402
from morm_l1.tx import Transaction              # noqa: E402

from web3 import Web3                            # noqa: E402
from eth_account import Account                  # noqa: E402

# ── config (defaults match the rest of the PoC) ───────────────────────────
EVM_RPC      = "http://127.0.0.1:8545"
MORM_RPC     = "http://127.0.0.1:8900"
BRIDGE_ADDR  = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"  # native ETH bridge
ERC20_BRIDGE_ADDR = None  # ERC-20 bridge (passed in via argv)
USDC_TOKEN_ADDR   = None  # USDC token (passed in via argv)
TREASURY_EVM_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
POLL_INTERVAL = 1.0


def get_morm(p):  return json.loads(urllib.request.urlopen(MORM_RPC + p, timeout=5).read())
def post_morm(p, b):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        MORM_RPC + p, method="POST",
        data=json.dumps(b).encode(),
        headers={"Content-Type": "application/json"}), timeout=5).read())


class Relayer:
    def __init__(self, treasury_seed_hex: str, bridge_addr: str,
                 erc20_bridge_addr: str | None = None,
                 usdc_addr: str | None = None):
        self.w3 = Web3(Web3.HTTPProvider(EVM_RPC))
        if not self.w3.is_connected():
            raise SystemExit("EVM RPC unreachable")
        self.bridge_addr = Web3.to_checksum_address(bridge_addr)

        # load ABIs from forge build artifacts
        out = ROOT / "morm-chain" / "out"
        artifact = json.loads((out / "MORMBridge.sol" / "MORMBridge.json").read_text())
        self.bridge = self.w3.eth.contract(address=self.bridge_addr,
                                            abi=artifact["abi"])

        self.erc20_bridge = None
        self.erc20_bridge_addr = None
        self.usdc_addr = None
        if erc20_bridge_addr and usdc_addr:
            erc_art = json.loads((out / "MORMBridgeERC20.sol" /
                                   "MORMBridgeERC20.json").read_text())
            self.erc20_bridge_addr = Web3.to_checksum_address(erc20_bridge_addr)
            self.erc20_bridge = self.w3.eth.contract(
                address=self.erc20_bridge_addr, abi=erc_art["abi"])
            self.usdc_addr = Web3.to_checksum_address(usdc_addr)

        # Treasury keys: same MORM seed (treasury) drives BRIDGE_MINT.
        # The EVM relayer key is the same anvil treasury key (#1).
        self.treasury_seed = bytes.fromhex(treasury_seed_hex.removeprefix("0x"))
        self.treasury_pub  = crypto.pubkey_from_seed(self.treasury_seed)
        self.treasury_addr = crypto.address(self.treasury_pub)
        self.evm_account   = Account.from_key(TREASURY_EVM_KEY)

        # cursors
        self.last_evm_block = self.w3.eth.block_number
        self.handled_lock_ids: set[str] = set()
        self.handled_burn_hashes: set[str] = set()

        # pre-warm the handled sets from the L1 ledger so we don't double-send
        for row in get_morm("/bridge/burns").get("burns", []):
            if row["evm_unlocked"]:
                self.handled_burn_hashes.add(row["burn_tx_hash"])

    # ── EVM → L1 (mint) ────────────────────────────────────────────────────
    def poll_evm_locks(self):
        head = self.w3.eth.block_number
        if head < self.last_evm_block:
            return

        # Native ETH bridge
        for ev in self.bridge.events.Locked().get_logs(
            from_block=self.last_evm_block, to_block=head):
            self._submit_mint(ev, token="MORM", token_address=None)

        # ERC-20 bridge (if configured)
        if self.erc20_bridge:
            for ev in self.erc20_bridge.events.TokenLocked().get_logs(
                from_block=self.last_evm_block, to_block=head):
                tok_addr = ev.args.token
                # map token address to symbol; PoC: just USDC
                symbol = "USDC" if tok_addr.lower() == self.usdc_addr.lower() else "TOKEN"
                self._submit_mint(ev, token=symbol, token_address=tok_addr)

        self.last_evm_block = head + 1

    def _submit_mint(self, ev, *, token: str, token_address: str | None):
        evm_id = f"evm:{ev.transactionHash.hex()}:{ev.logIndex}"
        if evm_id in self.handled_lock_ids:
            return
        # Phase 28a: write the BRIDGE_MINT recipient as the native m0r form
        # so the credited balance lands in the same account the rest of the
        # MORM UI (/wallet, /shop, etc.) reads from. The L1 still accepts
        # 0x-legacy (Phase 18 comment in state._tx_bridge_mint), but every
        # MORM-side surface that paints balances queries by m0r address.
        morm_addr = crypto.bytes20_to_address(bytes(ev.args.mormAddress))
        amount = int(ev.args.amount)
        print(f"[relayer] EVM Locked ({token}) → mint {amount} to {morm_addr} "
              f"(evm_lock_id={evm_id[:24]}…)")
        nonce = get_morm(f"/account/{self.treasury_addr}")["nonce"]
        tx = Transaction.bridge_mint(
            self.treasury_pub, nonce,
            to=morm_addr, amount=amount, evm_lock_id=evm_id,
            token=token, token_address=token_address,
        ).sign(self.treasury_seed)
        try:
            resp = post_morm("/tx", tx.to_dict())
            print(f"[relayer]   submitted: tx_hash={resp.get('tx_hash','?')[:16]}…")
            self.handled_lock_ids.add(evm_id)
        except Exception as e:
            print(f"[relayer]   mint failed: {e}")

    # ── L1 → EVM (unlock) ──────────────────────────────────────────────────
    def poll_morm_burns(self):
        burns = get_morm("/bridge/burns?only_pending=1")["burns"]
        for b in burns:
            h = b["burn_tx_hash"]
            if h in self.handled_burn_hashes:
                continue
            token = b.get("token") or "MORM"
            recipient = Web3.to_checksum_address(b["evm_recipient"])
            amount    = int(b["amount"])
            burn_id_b = bytes.fromhex(h)
            try:
                if token == "MORM":
                    tx = self.bridge.functions.unlock(
                        recipient, amount, burn_id_b,
                    )
                else:
                    if not self.erc20_bridge:
                        print(f"[relayer] no ERC-20 bridge configured for {token}, skipping")
                        continue
                    tx = self.erc20_bridge.functions.unlockToken(
                        self.usdc_addr, recipient, amount, burn_id_b,
                    )
                print(f"[relayer] MORM burn ({token}) → EVM unlock {amount} to {recipient} "
                      f"(burn_tx_hash={h[:16]}…)")
                nonce = self.w3.eth.get_transaction_count(self.evm_account.address)
                built = tx.build_transaction({
                    "from": self.evm_account.address,
                    "nonce": nonce, "gas": 200_000,
                    "gasPrice": self.w3.eth.gas_price, "chainId": 31337,
                })
                signed = self.evm_account.sign_transaction(built)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
                if receipt.status == 1:
                    print(f"[relayer]   unlock OK: evm_tx={tx_hash.hex()[:16]}…")
                    post_morm("/bridge/burn-confirmed", {"burn_tx_hash": h})
                    self.handled_burn_hashes.add(h)
                else:
                    print(f"[relayer]   unlock REVERTED: {tx_hash.hex()[:16]}…")
            except Exception as e:
                print(f"[relayer]   unlock failed: {e}")

    def run(self):
        print(f"[relayer] running. evm={EVM_RPC} morm={MORM_RPC} "
              f"bridge={self.bridge_addr}")
        print(f"          treasury L1 addr = {self.treasury_addr}")
        print(f"          treasury EVM addr= {self.evm_account.address}")
        while True:
            try:
                self.poll_evm_locks()
                self.poll_morm_burns()
            except Exception as e:
                print(f"[relayer] poll error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    treas = json.loads(Path("/tmp/k_treas.json").read_text())
    bridge_addr      = sys.argv[1] if len(sys.argv) > 1 else BRIDGE_ADDR
    erc20_bridge     = sys.argv[2] if len(sys.argv) > 2 else None
    usdc_addr        = sys.argv[3] if len(sys.argv) > 3 else None
    Relayer(treas["seed_hex"], bridge_addr,
            erc20_bridge_addr=erc20_bridge, usdc_addr=usdc_addr).run()

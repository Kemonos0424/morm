# MORM Bridge — design note (Phase 12 / 13 / 28a / 28b / 13b future)

> Last sync: 2026-05-01

This is the operational reference for the EVM ↔ MORM Chain bridge. Whitepaper
references: `MORM.md §1, §4, §9.5`. Forge/Echidna sign-off: Phase 26f.

## 1. Threat model

The bridge converts assets between two ledgers that share no common consensus.
Soundness reduces to:

- **No double-mint** on MORM L1 for a single EVM `Locked` event (replay
  protection in `bridge_mints.evm_lock_id` UNIQUE).
- **No double-unlock** on EVM for a single MORM L1 BRIDGE_BURN
  (`MORMBridge.unlocked[mormBurnId]` mapping).
- **Solvency**: bridge contract balance ≥ Σ(active locks) − Σ(unlocks).
  Echidna invariant 4/4 PASS in Phase 26f (`MORMBridgeMS`).
- **Liveness**: a censored MORM L1 burn is recoverable as long as ≥ M of N
  validators are honest (Phase 13b future model).

## 2. Three deployed contracts

| Contract | Asset | Trust model | Status |
|---|---|---|---|
| `MORMBridge` | native ETH | single relayer (treasury PoC) | Phase 12 — Forge 7/7 PASS |
| `MORMBridgeERC20` | arbitrary ERC-20 (USDC) | single relayer | Phase 13a — Forge 4/4 PASS |
| `MORMBridgeMS` | native ETH | M-of-N signatures bundled into `unlock()` | Phase 13b — Forge 5/5 + Echidna 4/4 (Phase 26f) |
| `MORMBridgeOptimistic` | native ETH | propose → challenge window → finalize | Phase 13c — Forge 5/5 PASS |

PoC (Phases 28a/28b) deploys `MORMBridge` + `MORMBridgeERC20` and runs them
behind the same `relayer.py`.

## 3. The Phase 28a/28b pipeline (single relayer)

```
┌──────────────┐   lock(bytes20)   ┌────────────┐    Locked event     ┌──────────────┐
│ EVM caller   │──────────────────▶│ MORMBridge ├────────────────────▶│  relayer.py  │
│ (MetaMask)   │                   └────────────┘                     └──────┬───────┘
└──────────────┘                                                            │ BRIDGE_MINT (kind=20)
                                                                            ▼
                                                                     ┌──────────────┐
                                                                     │  MORM L1     │
                                                                     └──────┬───────┘
                                                                            │ /account/<m0r>.balance += amount
```

Reverse direction:

```
┌──────────────┐  BRIDGE_BURN (kind=21)  ┌──────────────┐  /bridge/burns?only_pending=1
│ /swap (Burn) ├────────────────────────▶│   MORM L1    ├────────────┐
│  passkey-sig │                          └──────────────┘            ▼
└──────────────┘                                              ┌──────────────┐
                                                              │  relayer.py  │
                                                              └──────┬───────┘
                                                                     │ unlock(recipient, amount, burnId)
                                                                     ▼
                                                              ┌──────────────┐
                                                              │  MORMBridge  │
                                                              │  (release)   │
                                                              └──────────────┘
```

### 3.1 Why separate native vs ERC-20 contracts

`MORMBridge.lock(bytes20) payable` accepts ETH directly via `msg.value`. ERC-20
tokens can't ride on `msg.value`, so `MORMBridgeERC20.lockToken(token, amount,
mormAddr)` requires a prior `approve()` and pulls via `transferFrom`. Same
shape on the L1 side: `BRIDGE_MINT` payload carries `token: 'MORM' | 'USDC' | ...`
and `token_address`, the L1 routes the credit to either the native `accounts.balance`
column (token=MORM) or the per-token `account_tokens` mirror table (token≠MORM).

### 3.2 USDC 6-decimal vs ETH 18-decimal

USDC integers in payloads/UI are **raw 6-decimal int** (`100 USDC = 100_000_000`).
ETH integers are **wei** (`0.5 ETH = 500_000_000_000_000_000`). The L1 stores
both as i64 — USDC fits trivially, ETH wei fits up to ~9.2 ETH per single
balance row (`2^63 ≈ 9.22 × 10^18`). For PoC this is sufficient; production
would migrate L1 balance columns to a wider integer type (or denominate ETH in
gwei).

### 3.3 m0r vs 0x recipient form (Phase 28a fix)

The relayer originally wrote BRIDGE_MINT payloads with `recipient = "0x" +
bytes(mormAddr).hex()`. That credited a *different* L1 account row from the
m0r-prefixed form returned by `crypto.address(pub)`, so the mint balance
landed in an account separate from the user's `/wallet` view. Phase 28a fix:
relayer now uses `crypto.bytes20_to_address(bytes(mormAddr))` so the credit
lands in the canonical m0r account. The L1 side still accepts both forms
(`state._tx_bridge_mint` Phase 18 comment) for legacy compatibility.

## 4. /swap UI (Phase 28a/28b)

Three tabs on `morm-player/static/swap.{html,js}`:

| Tab | Lock side (EVM → L1 mint) | Burn side (L1 → EVM unlock) | Wallet |
|---|---|---|---|
| **Lock ETH** | `MORMBridge.lock(bytes20)` via MetaMask | n/a | MetaMask EOA (Lock) |
| **Burn → ETH** | n/a | `BRIDGE_BURN { amount, evm_recipient }` via passkey | passkey (walletless) |
| **USDC** | sub: `approve` + `lockToken(usdc, amt, bytes20)` via MetaMask <br/> sub: `BRIDGE_BURN { token:'USDC', token_address, evm_recipient }` via passkey | | both |

Bridge-status panel auto-refreshes every 5s by direct `eth_call` against
`lockNonce()` / `unlockNonce()` and `balanceOf(bridgeAddr)` for USDC, plus
`/bridge/burns?only_pending=1` for L1 pending count.

The page is driven by:
- `/api/morm/bridge` → `{ bridge_addr, evm_rpc, evm_chain_id, erc20_bridge_addr, usdc_addr }`
- `/api/morm/info` → `{ rpc, treasury, ... }`
- `/api/relay/morm-tx` → POST passkey-signed BRIDGE_BURN
- `/api/dev/share` → server share for 2-of-2 XOR seed reconstruction

The USDC tab is hidden client-side until both `erc20_bridge_addr` and
`usdc_addr` are populated, so a gateway started without the ERC-20 flags
shows only the original ETH tabs.

## 5. Phase 13b future — M-of-N migration

Today (PoC) the relayer is a single trusted entity that holds the treasury
seed. To remove that single point of compromise:

### 5.1 EVM side — already in place

`MORMBridgeMS.sol` has been deployed-tested: it accepts `unlock(recipient,
amount, burnId, signatures[])` where `signatures` is an array of (r,s,v) ECDSA
sigs over the digest `keccak256(abi.encode(this, chainid, "MORMBridgeMS:unlock",
recipient, amount, burnId))`. The contract enforces:

- ≥ `threshold` (M) distinct signatures from `signers[]` (N)
- ascending signer-address ordering for dedup
- each `mormBurnId` is one-shot

### 5.2 L1 side — already in place

Phase 26a (treasury multi-sig) registered the same M-of-N validator pubkeys
as `treasury_signers` on the L1. Treasury-only kinds (BRIDGE_MINT, FINALIZE,
REGISTER_PRODUCER, REGISTER_AI_SERVICE) can no longer be signed by a single
key — they must arrive wrapped in `MULTISIG_TX(inner_tx)` with M cosignatures
over `multisig_signing_bytes(inner_kind, payload, treasury_addr, treasury_nonce)`.

### 5.2.1 Phase 13b PoC E2E — manual orchestration (2026-05-01)

To prove the protocol works end-to-end before investing in a full validator
mesh, `scenario_swap_quorum.py` exercises the full lock-mint-burn-unlock loop
in a single process with **all three validators present in memory**. This
verifies the contract+chain machinery; only the inter-validator gossip layer
is still future work.

Setup:

- Anvil :8545 + `MORMBridgeMS` deployed via `script/DeployBridgeMS.s.sol` with
  3 anvil signers (#5/#6/#7) sorted ascending, threshold = 2.
- Fresh L1 :8910 (`/tmp/morm-l1-quorum`) booted with a bootstrap treasury seed
  (no genesis lockdown). The producer is a separate ed25519 key.
- 3 ed25519 validator seeds + the bootstrap treasury seed in
  `/tmp/quorum-keys.json` (file mode 0600).

Flow (each step labelled in scenario stdout):

1. Treasury submits `REGISTER_TREASURY_SIGNERS({signers: [v0,v1,v2], threshold: 2})`
   — single-key bootstrap, exactly once (state.py rejects re-registration
   without a wrapper).
2. Alice (anvil #2) calls `MORMBridgeMS.lock(bytes20)` with 0.05 ETH and a
   freshly-generated m0r recipient.
3. The script fabricates the inner BRIDGE_MINT payload from the Locked event
   (`{to: alice_morm, amount: 0.05 ETH wei, evm_lock_id, token: 'MORM'}`),
   reads `treasury_nonce` from the L1, computes `multisig_signing_bytes`,
   and signs once per validator.
4. Validator-0 wraps the inner tx in `MULTISIG_TX` with the first 2
   cosignatures and POSTs to /tx. State.py verifies threshold + signer
   membership + nonce match, then dispatches the inner BRIDGE_MINT through
   `_tx_bridge_mint` with sender = treasury. The credit lands on alice_morm.
5. Alice signs `BRIDGE_BURN { amount: 0.02 ETH wei, evm_recipient: bob }`
   on the L1.
6. Each validator signs the EVM `unlockDigest(bob, 0.02 ETH, burn_id)` using
   eth_sign-style prefixing (encode_defunct).
7. The 2 sigs with the lowest signer addresses are chosen (the contract
   requires ascending order to dedup). Validator-0 calls
   `MORMBridgeMS.unlock(bob, 0.02 ETH, burnId, sigs[])`.

Observed (2026-05-01): all 7 steps green, bob EVM Δ = 0.02 ETH, alice L1
balance 0.03 ETH = 0.05 mint − 0.02 burn, bridge contract released the ETH
correctly. **No single-key relayer was involved at any step.**

Run:

```bash
# 1. (one-time) deploy MORMBridgeMS
cd morm-chain && PATH="/opt/homebrew/bin:$PATH" forge script \
    script/DeployBridgeMS.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
# Capture the deployed addr to /tmp/bridge_ms_addr.txt

# 2. (one-time) start fresh L1 with bootstrap treasury
cd morm-l1 && .venv/bin/python -m morm_l1.cli node \
    --data-dir /tmp/morm-l1-quorum \
    --producer-seed $PROD_SEED \
    --treasury m0ro5wwfg7o7tdpr5c5ebbzsss6q3rxzu3q \
    --port 8910 --genesis-lockdown-height 0 &

# 3. run the scenario
cd .. && morm-l1/.venv/bin/python scenario_swap_quorum.py
```

### 5.3 Off-chain — what remains for Phase 13b

The relayer currently shipping is a single-process Python script. The Phase
13b migration ships **N independent validator processes**. Each one:

1. Watches the EVM (`Locked` / `TokenLocked` events) and the L1
   (`bridge_burns` table) like today.
2. **Mint side**: instead of submitting `BRIDGE_MINT` directly, signs the inner
   tx and gossips the cosignature to peers. Once any node has ≥ M cosignatures
   it wraps the inner tx in `MULTISIG_TX` and posts to `/tx`.
3. **Unlock side**: signs the EVM `unlock()` digest with its EVM key
   (different from the L1 ed25519 key) and gossips the (r,s,v). Once any node
   has ≥ M ECDSA sigs it bundles them into a `MORMBridgeMS.unlock(...,
   signatures[])` call.

Open design choices (next session):

- **Gossip transport**: HTTP `/relayer/cosignature` POST (simple) vs reusing
  the QUIC mesh from Phase 25a (consistent). Recommend HTTP for the PoC; the
  cosignature volume is tiny (one per bridge event) and the validator set is
  static and small.
- **Slot leadership**: which node submits the aggregated tx? Either every
  node tries (idempotent, wastes gas) or rotate based on `(burn_hash %
  N == self.id)`. Recommend rotation with fallback timeout.
- **Validator key on-disk**: each validator needs both its ed25519 (L1) and
  its secp256k1 (EVM) key. Reuse the Phase 26x `--treasury-key-file` mode
  with two files: `--multisig-l1-keyfile` + `--multisig-evm-keyfile`.
- **Bootstrap**: registered via on-chain `REGISTER_TREASURY_SIGNERS` once,
  during testnet genesis, by the bootstrap treasury key. After bootstrap that
  initial single key is retired.

Estimated effort (remaining): ~4-5h to extract the in-process orchestration
in `scenario_swap_quorum.py` into N separate validator processes with HTTP
cosignature gossip, +~2h for liveness/timeout tests.

Status: **protocol layer green** (Phase 13b PoC PASS, see §5.2.1). The
remaining work is purely the off-chain coordination layer.

## 6. Open issues / future work

- **Treasury MORM cap depletion**: PoC genesis allocates `10^18 µMORM` to
  treasury. After multiple lock cycles the cap can deplete and BRIDGE_MINT
  silently fails (relayer doesn't check `resp.ok`). Production wants
  unlimited treasury (i.e. mint-on-demand) or a wider int balance type.
- **Optimistic bridge** (`MORMBridgeOptimistic.sol`, Phase 13c) is deployed-
  tested but has no relayer integration yet. Could replace MS for some
  asset classes.
- **Real-MetaMask in-browser test for /swap** — preview iframe doesn't
  inject `window.ethereum`, so the Lock side has only been validated
  programmatically (`scenario_swap.py`). Real Chrome tab + MetaMask test is
  a one-time manual verification.
- **scenario_swap.py treasury-cap edge**: when treasury runs out, the relayer
  log shows `submitted: tx_hash=…` but the L1 silently rejects. Add a `resp.ok`
  check + retry/log in `relayer._submit_mint`.

## 7. Reference: deployed addresses (Anvil 31337, 2026-05-01 PoC)

```
MORMBridge       (ETH)   = 0x5fbdb2315678afecb367f032d93f642f64180aa3
MORMBridgeERC20  (USDC)  = 0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0
MockUSDC                 = 0xe7f1725e7734ce288f8367e1bb143e90bb3f0512
treasury (relayer EVM)   = 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 (anvil acct #1)
treasury (relayer L1)    = m0r3or65m6jbnlb6fnd2nvylah23vo54dky
```

For setup commands see `reference_morm_session_handoff_20260501.md §0.6`.

## 8. Reference: function selectors (cast sig)

```
MORMBridge.lock(bytes20)                              0x9de746a5
MORMBridge.unlock(address,uint256,bytes32)            0xb322edea
MORMBridge.lockNonce()                                0xb5a9096e
MORMBridge.unlockNonce()                              0xdd926714
MORMBridgeERC20.lockToken(address,uint256,bytes20)    0x8b1a8f0d
ERC-20 approve(address,uint256)                       0x095ea7b3
ERC-20 balanceOf(address)                             0x70a08231
ERC-20 allowance(address,address)                     0xdd62ed3e
MockUSDC.mint(address,uint256)                        0x40c10f19
```

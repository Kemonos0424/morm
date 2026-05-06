# Security policy

This is a research-grade open-source project. The contents of this repo
are PoC-quality with explicit hardening phases (26a-z, 27f/g/h/i, 28a/b)
and a documented threat model in
[`morm-l1/ops/SECURITY-DESIGN.md`](morm-l1/ops/SECURITY-DESIGN.md).

## Reporting a vulnerability

If you find a vulnerability, **please do not open a public issue**.
Instead:

1. Open a [GitHub Security
   Advisory](https://github.com/Kemonos0424/morm/security/advisories/new)
   on this repo. The maintainer will see it privately.
2. If you can't access the Security Advisories tab (forks etc.), email
   `90598769+Kemonos0424@users.noreply.github.com` with the word
   `[security]` in the subject. The maintainer will reply within 7 days.

Please include:

- A description of the vulnerability
- Reproduction steps (a minimal scenario script if possible)
- Suggested mitigation (optional)

## Disclosure timeline

- We aim to acknowledge reports within 7 days
- Initial assessment within 14 days
- Coordinated disclosure once a fix is in `main` and tagged
- We credit reporters in release notes unless they prefer to remain anonymous

## Scope

In scope:

- The L1 chain (`morm-l1/morm_l1/`) — consensus, state, gossip, mempool
- The Solidity contracts (`morm-chain/src/`) — bridge contracts, escrow
- The browser gateway (`morm-player/passkey_morm.py` + `static/`) —
  passkey, tx confirm dialog, wallet policy
- The relayer (`relayer.py`) and quorum scenarios
- Docker images we publish to ghcr.io
- The federation seed loader (`morm-l1/morm_l1/seed_loader.py`)

Out of scope:

- Third-party dependencies (cryptography, aioquic, web3, eth-account,
  webauthn, FFmpeg, hls.js, MetaMask). Report to upstream first.
- The example test fixtures (anvil deterministic keys, scenario_*.py
  test data — these are PoC fixtures with NO production value).
- Speculative attacks on planned but unreleased features (Phase 13b
  N-validator gossip, Phase 29 multi-passkey, Phase 30f tunnels).

## Known intentional design decisions (NOT vulnerabilities)

- **Anvil deterministic keys (`0xac09…2ff80` etc.) are committed in
  scenario scripts.** These are public test keys built into Foundry
  itself; they only have funds on local Anvil chains and are useless on
  any other network.
- **Treasury m0r-prefixed addresses are public by design.** Security
  comes from the corresponding ed25519 seed (which is operator-local
  and never committed). Publishing addresses is fine.
- **`MORM_PRODUCTION=1` env hard-disables `--dev-mode`.** The `--dev-mode`
  flag is intentional for local development and refused outright in
  production via Phase 26w guard.
- **`docker/.env.example`** intentionally has empty values. Real config
  goes in `docker/.env` which is gitignored.
- **`GENESIS_HASH = b"\x00" * 32`** is universal across networks. Forks
  with different `treasury` addresses produce different state_root and
  are naturally separated.
- **Federation `seeds.json` ships with `seeds: []` (empty)** so a fresh
  node never connects to peers it didn't knowingly accept.

## Hardening phases shipped (excerpt)

| Phase | Mitigation |
|---|---|
| 26a | Treasury multi-sig (M-of-N for treasury-only tx kinds) |
| 26b/24d | Per-producer block rate limit |
| 26c | Mempool global cap + per-sender quota |
| 26e | Genesis lockdown window (eclipse defense) |
| 26f | Slither High=0 + Echidna 4/4 PASS for bridge contracts |
| 26q | P2P content poisoning defense (SHA256 vhash verify) |
| 26r/s | Signaling DoS guards (per-IP rate / mailbox / peers cap) |
| 26u/v | CSRF + strict CORS for the gateway |
| 26w | Production mode dev-mode lockout |
| 26x | Treasury keyfile (mode 0o600 enforced, `ps` leak defense) |
| 26y | Service Worker version check + 24h cache TTL |
| 27f | Tx confirm dialog before passkey signing |
| 27g/h/i | Per-app spend cap + tx kind whitelist + 1-tap revoke |
| 13b-PoC | M-of-N quorum bridge (no single-key relayer required) |

For the full table see
[`docs/IMPLEMENTATION-STATUS.md`](docs/IMPLEMENTATION-STATUS.md) and
[`morm-l1/ops/SECURITY-DESIGN.md`](morm-l1/ops/SECURITY-DESIGN.md).

## Things we explicitly do NOT do

- We don't run a privileged registry. Image distribution is via
  ghcr.io public images; anyone may fork and host their own mirror.
- We don't depend on a single DNS zone. The federation seed list ships
  with `dns_seed: null`; operators wanting DNS-driven discovery must
  point at a domain THEY control.
- We don't ship a default treasury seed. `docker/init.sh` always
  generates a fresh one on first boot, mode 0o600.
- We don't operate behind an LLC. There is no privileged off-chain
  authority that could be compelled to alter the protocol.

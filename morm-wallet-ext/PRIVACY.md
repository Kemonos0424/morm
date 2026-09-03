# MORM Wallet — Privacy Policy

_Last updated: 2026-09-04_

MORM Wallet is a **non-custodial** browser extension for the MORM network. Your
keys are generated and stored **on your device only**. We do not run servers that
receive, hold, or have access to your private keys, seed, or recovery key.

## What the extension stores (on your device only)

- Your wallet as **AES-GCM ciphertext** (the encrypted 32-byte ed25519 seed) plus
  its key-derivation parameters, in the browser's local extension storage.
  The decryption key is derived either from your **password** (PBKDF2) or from a
  **passkey** (WebAuthn PRF) — the plaintext seed is never written to disk.
- A short-lived **unlocked session** in `chrome.storage.session` (RAM only,
  cleared when the browser closes, and auto-locked after 5 minutes idle) so you
  don't re-authenticate for every action.

None of this is transmitted anywhere. There is no account, sign-up, analytics,
tracking, advertising, or telemetry.

## What the extension sends over the network

Only to the MORM network's own endpoints, and only to operate your wallet:

- **api.morm.one / l1.morm.one** — read your balance and nonce; relay
  transactions **you** signed on your device (transfers, bridge).
- **node.morm.one** — read your own node status and reward history (read-only).

Requests contain your public MORM address (needed to look up your public
on-chain balance) and, for transactions, the transaction **you already signed**.
Your private key/seed/recovery key are never sent.

## Passkey / biometrics

Passkey unlock uses your platform authenticator (Touch ID, Windows Hello, etc.)
via WebAuthn with RP ID `morm.one`. Biometric data never leaves your device and
is never seen by the extension or by us — only a derived secret is used to
unlock your local wallet.

## Clipboard

When you copy your recovery key, the extension clears it from the clipboard
after ~20 seconds to reduce exposure. Clipboard contents are never read or sent.

## External sites

"Swap" and "deposit from Base" open **morm.one** in a normal browser tab; those
actions happen on the website with your EVM wallet (e.g. MetaMask), not inside
this extension.

## Data sharing & sale

We do **not** sell, rent, or share your data. We do not use it for anything
other than operating the wallet at your request.

## Contact

Questions: open an issue at https://github.com/Kemonos0424/morm

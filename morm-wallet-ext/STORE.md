# Chrome Web Store — submission package

Everything needed to list **MORM Wallet**. Fill the CWS Developer Dashboard with
the fields below.

## 0. Prerequisites (user actions)

- **CWS developer account** (one-time $5) — https://chrome.google.com/webstore/devconsole
- **Privacy policy hosted at a public URL** — deploy `PRIVACY.md` as HTML/text,
  e.g. `https://morm.one/wallet/privacy` (drop into `site/` and deploy like the
  rest of morm.one). The URL is required in the listing.
- Decide the **version**: `manifest.json` is `0.0.1`. Bump to `1.0.0` for the
  first public release if you prefer.

## 1. Package

Zip the built extension (with `walletcore/` present — it is gitignored, so build
first):

```bash
cd morm-wallet-ext
node tools/build_ext.mjs
( cd extension && zip -r ../morm-wallet.zip . -x '.*' )
```

Upload `morm-wallet.zip`.

### Extension ID / signing key
`manifest.json` contains a `"key"` (public key) that pins the ID
`enmmpmpjbdplcglnncnkjbebehddbeka`. Keep the matching **private key**
`morm-ext-key.pem` (currently in your scratchpad, NOT in the repo) safe — it
maintains the same ID across dev and store. Do **not** commit it.

## 2. Listing text

- **Name**: MORM Wallet
- **Summary (≤132 chars)**: Non-custodial MORM wallet — hold, send, bridge to Base, and view your node. Keys stay encrypted on your device.
- **Category**: Productivity
- **Language**: Japanese (primary), English
- **Detailed description**:

  > MORM Wallet is the official non-custodial wallet for the MORM network.
  >
  > • Hold, send, and receive MORM (m0r… addresses)
  > • Bridge MORM to Base as wMORM
  > • View your MORM node status and reward history
  > • Unlock with a password or your morm.one passkey (biometrics)
  >
  > Your keys are generated and stored encrypted on your device only. Nothing is
  > sent to any server except your own signed transactions and public balance
  > lookups on the MORM network. No account, no tracking, no ads.
  >
  > Swapping and depositing from Base open morm.one in your browser and use your
  > EVM wallet.

## 3. Single purpose (required)

> A non-custodial wallet for the MORM network: hold MORM, send/receive, bridge to
> Base, and view your node — with private keys stored encrypted on the user's
> device.

## 4. Permission justifications (required per item)

- **storage**: Stores the user's wallet as AES-GCM ciphertext (encrypted seed) and
  a short-lived in-RAM unlock session. No plaintext key is stored; nothing is
  transmitted.
- **clipboardWrite**: Lets the user copy their address and recovery key, and
  auto-clears the recovery key from the clipboard after ~20s for safety.
- **host: api.morm.one**: Read the user's public balance/nonce and relay the
  transactions they signed on-device.
- **host: l1.morm.one**: Read MORM L1 node state (balances).
- **host: node.morm.one**: Read the user's own node status and reward history
  (read-only).
- **host: morm.one, www.morm.one**: Required so the extension can use the user's
  morm.one passkey for biometric unlock — Chrome requires a WebAuthn `rp.id` to be
  listed in the extension's host_permissions.
- **externally_connectable (morm.one)**: Reserved for a future secure hand-off
  from morm.one; no data is exchanged yet.

## 5. Privacy practices (data disclosures)

- Does the extension collect/use user data? **Handles wallet data locally only.**
- Sells data: **No.** Uses data for unrelated purposes: **No.** Uses/transfers for
  creditworthiness/lending: **No.**
- Remote code: **No** (all JS is bundled; no external scripts — strict CSP).
- Data in transit is limited to public address lookups and user-signed
  transactions to MORM endpoints (see PRIVACY.md).

## 6. Graphics

- **Store icon 128×128**: `extension/icons/store-128.png` (MORM mark). ✓ generated
- **Screenshots (required, 1–5)**: 1280×800 or 640×400 PNG/JPG. Suggested shots:
  1. Home — balance + address + tabs (send/bridge/node)
  2. Send — confirm screen (address + amount + kind)
  3. Bridge — L1→Base with linked Base address
  4. Node tab — node status + reward history
  5. Unlock — passkey/password
  (Ask Claude to generate these at 1280×800 from the UI if needed.)
- **Small promo tile 440×280** (optional).

## 7. Review-risk notes (crypto wallets are scrutinized)

- **Non-custodial, single purpose, no remote code, strict CSP** — all favorable.
- **No in-app buying/selling of crypto and no fiat**: swap & Base deposit are
  external hand-offs to morm.one (keeps the binary clear of purchase flows that
  trigger IAP/financial-product review).
- **Node "rewards" are display + external binding only** — the extension does not
  pay out or promise returns; it reads status and links a reward address.
- Provide the **privacy policy URL** and clear permission justifications above.

## 8. After first publish

- The store may assign an ID; keeping `"key"` + `morm-ext-key.pem` keeps it stable
  at `enmmpmpjbdplcglnncnkjbebehddbeka`. Passkey unlock is unaffected by any ID
  change (it depends on the morm.one host permission, not the extension ID).
- Updates: bump `manifest.json` version, re-zip, upload a new version.

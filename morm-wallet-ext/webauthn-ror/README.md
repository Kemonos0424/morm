# Passkey Related Origin Requests (ROR) — morm.one setup

To let the MORM Wallet **Chrome extension unlock with the same passkey** that
`morm.one/account.html` created (`RP_ID = morm.one`), the site must publish a
Related Origins file so WebAuthn allows the extension's origin to assert against
`rpId: "morm.one"`.

## Deploy step (on morm.one)

Serve `webauthn.json` at exactly:

```
https://morm.one/.well-known/webauthn
```

- `Content-Type: application/json`
- Publicly readable, no auth, no redirect.
- Requires Chrome 128+ on the client (the extension surface).

## Origins list

- `chrome-extension://enmmpmpjbdplcglnncnkjbebehddbeka` — **dev / unpacked** build
  (derived from the pinned `key` in `extension/manifest.json`).
- ⚠️ After first Chrome Web Store publish, the **store assigns a different
  extension ID**. Add that `chrome-extension://<store-id>` to the `origins`
  array too (ROR allows up to 5 origins). Until then, only the dev build can use
  the shared passkey.

## How the extension uses it

The extension calls `navigator.credentials.get({ rpId: "morm.one", extensions:
{ prf: { eval: { first: PRF_SALT } } } })` with `PRF_SALT = "morm-wallet-prf-v1"`
(see `@morm/wallet-core` `vault.js`). With ROR in place the platform returns the
**same PRF secret** account.html gets, so `aesKeyFromPRF` derives the same
AES-GCM key. The encrypted seed itself must still be imported into the extension
once (recovery key, or the future morm.one→extension ciphertext handoff) because
IndexedDB is origin-isolated.

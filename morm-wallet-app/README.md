# MORM Wallet — mobile app (Capacitor)

Wraps the **existing wallet web UI + `@morm/wallet-core`** (from `morm-wallet-ext`)
as a native iOS/Android app. Maximum reuse: the popup UI, `wallet.js`, `passkey.js`,
`config.js`, and `walletcore/` are copied **verbatim**; only the storage substrate
is swapped via `www/chrome-shim.js`.

## What differs from the extension
- **Storage**: `chrome.storage.local` → Capacitor **Preferences** (native);
  `chrome.storage.session` → in-memory (RAM, gone on app kill). Shim: `www/chrome-shim.js`.
- **Network/CORS**: `CapacitorHttp` is enabled (`capacitor.config.json`) so
  `fetch()` uses native HTTP and bypasses browser CORS to api/l1/node.morm.one.
- **No Service Worker / `chrome.runtime`** (mobile has none).
- **Passkey**: WebAuthn works only on iOS 17+/modern Android WebView; native
  passkey + associated-domains is a later step (password unlock works today).

## Layout
```
morm-wallet-app/
  capacitor.config.json      appId one.morm.wallet, CapacitorHttp enabled
  package.json               @capacitor/{core,cli,ios,android,preferences}
  www/chrome-shim.js         Preferences/localStorage-backed chrome.* shim (committed)
  tools/build_app.mjs        assembles www/ from ../morm-wallet-ext/extension
  www/ (generated)           index.html + reused JS + walletcore/ (gitignored)
  ios/ android/ (generated)  native projects (gitignored)
```

## Build / run
```bash
npm install
npm run build:www            # assemble www/ from the extension (reuse)
npx cap add ios              # first time (pod install)
npx cap sync
npx cap open ios             # build & run from Xcode (Simulator or device)
```

### ⚠️ Prerequisite: full Xcode (not just Command Line Tools)
iOS build/Simulator needs **Xcode.app** from the Mac App Store. This machine
currently has only Command Line Tools (`xcode-select -p` →
`/Library/Developer/CommandLineTools`). Install Xcode, then:
```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

### CocoaPods note
`pod install` on this machine needs a UTF-8 locale (Ruby 4 + ASCII-8BIT bug):
```bash
cd ios/App && LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 pod install
```

### Android
Needs Android Studio + SDK (`ANDROID_HOME`). Then `npx cap add android`.

## Status
- ✅ Capacitor project scaffolded; deps installed; **iOS platform added + pods installed**.
- ✅ Web layer verified in a mobile viewport (create/unlock/home via the shim).
- ⏳ Native build/run pending **full Xcode** install.
- ⏳ Later: native secure storage (Keychain/Keystore), native passkey + associated
  domains, app-store assets/metadata.

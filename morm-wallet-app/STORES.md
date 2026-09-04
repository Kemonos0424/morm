# MORM Wallet — App store registration & submission

Reference for shipping MORM Wallet to each store. Bundle/app id: **`one.morm.wallet`**.
Reusable listing text, permission justifications, and the privacy policy live in
`../morm-wallet-ext/STORE.md` and `../morm-wallet-ext/PRIVACY.md`
(hosted at https://morm.one/wallet/privacy.html).

Shared assets:
- App icon source: `assets/icon.png` (1024) — brand mark.
- Splash: `assets/splash.png` / `assets/splash-dark.png` (2732).
- Screenshots: `../morm-wallet-ext/store-assets/` (1280×800; regenerate per device size as needed).

---

## 1) Chrome Web Store (extension) — DONE / in review

- Console: https://chrome.google.com/webstore/devconsole
- Publisher: MORM (goldman424@gmail.com, verified). Item id `bflglppbnplbjcglfhmkkkaengdkfcoc`.
- **Status: submitted for review (2026-09-04).** See `../morm-wallet-ext/STORE.md`.
- Reminder: the store zip must NOT contain manifest `key` (strip it — see STORE.md §1).

---

## 2) Apple App Store (iOS)

**Cost:** Apple Developer Program **$99 / year**. **Gates everything below** (Team ID,
signing, TestFlight, App Store, and native passkey).

### A. Enroll
1. https://developer.apple.com/programs/ → Enroll with the Apple ID.
   - **Individual** (fast, name shown as your legal name) or **Organization**
     (needs a D-U-N-S number; name shown as the company). Wallets are fine as
     individual for launch.
2. Accept agreements in **App Store Connect** (https://appstoreconnect.apple.com);
   fill Agreements/Tax/Banking if ever charging (not needed for a free app).
3. Note your **Team ID** (Membership page) — needed for signing + passkey AASA.

### B. Register the app
1. **Certificates, IDs & Profiles** → App IDs → register `one.morm.wallet`
   (enable capabilities you use: **Associated Domains** for passkey).
2. **App Store Connect** → Apps → **＋** → new app, bundle `one.morm.wallet`,
   name "MORM Wallet", primary language Japanese, SKU any.

### C. Sign & build
1. Open the project: `npm run ios`  (or `npx cap open ios`).
2. In Xcode → target **App** → Signing & Capabilities → check **Automatically
   manage signing**, pick the Team → Xcode creates certs/provisioning.
3. Set version/build; **Product → Archive** (device, not simulator).
4. **Distribute App → App Store Connect → Upload** (or export .ipa → Transporter).

### D. Native passkey (optional but planned — needs B/C first)
- In Xcode add **Associated Domains** entitlement:
  `webcredentials:morm.one`
- Publish `https://morm.one/.well-known/apple-app-site-association` (JSON,
  content-type application/json) containing:
  ```json
  { "webcredentials": { "apps": ["<TEAM_ID>.one.morm.wallet"] } }
  ```
  (Deploy to the ts-mini apex like the ROR file — `.well-known` is already allowed
  by `morm-apex.conf`.)
- Then WebAuthn (rpId=morm.one) works in the app's WKWebView = same passkey as web.

### E. Listing & submit
- Screenshots (6.7"/6.5"/iPad as required), icon (App Store Connect uses the
  archived 1024 icon), description/keywords, **privacy policy URL**
  `https://morm.one/wallet/privacy.html`, App Privacy questionnaire
  (no data collected — keys stay on device), category Finance or Utilities.
- **Crypto review notes:** non-custodial wallet is allowed; **no in-app buying/
  selling of crypto and no fiat** (swap/deposit are external hand-offs to
  morm.one). Do not add IAP. Answer the encryption-export question (uses only
  standard crypto → usually exempt; may need a French declaration).
- Submit for **App Review** (a few days). Use **TestFlight** first for real-device
  testing (internal testers need no review).

---

## 3) Google Play (Android)

**Cost:** Google Play Console **$25 one-time**. Cheaper/faster than Apple — good
first public distribution.

### A. Enroll
1. https://play.google.com/console → create a developer account ($25 once).
   Choose **personal** or **organization**; complete identity verification
   (D-U-N-S for org; personal needs ID). Verification can take a day or two.

### B. Create the app
1. Console → **Create app**: name "MORM Wallet", language 日本語, **app** (not game),
   **Free**. Accept declarations.
2. Package name is set by the uploaded bundle: **`one.morm.wallet`** (final once
   uploaded — cannot change later).

### C. Signing & build (AAB)
1. Enroll in **Play App Signing** (default): you upload an **AAB** signed with an
   **upload key**; Google re-signs with the app key.
2. Create an upload keystore (keep it safe — losing it needs a key reset):
   ```bash
   keytool -genkey -v -keystore morm-upload.jks -alias morm \
     -keyalg RSA -keysize 2048 -validity 10000
   ```
   (Store `morm-upload.jks` OUTSIDE the public repo, like the extension key.)
3. Configure `android/app/build.gradle` `signingConfigs.release` (or use
   `android/keystore.properties`, gitignored) → build:
   ```bash
   export ANDROID_HOME="$HOME/Library/Android/sdk"
   export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
   ( cd android && ./gradlew bundleRelease )   # -> app/build/outputs/bundle/release/app-release.aab
   ```

### D. Store listing & compliance
- **Main store listing:** short + full description (reuse STORE.md text), app icon
  512×512 (`npx @capacitor/assets` output or resize `assets/icon.png`), feature
  graphic 1024×500, phone screenshots (≥2). 
- **Privacy policy:** `https://morm.one/wallet/privacy.html`.
- **App content:** Data safety form (no data collected/shared — keys on device),
  content rating questionnaire, target audience, ads = none, government/financial
  features declaration (non-custodial wallet), news = no.
- **Crypto policy:** Google allows non-custodial wallets; declare it's a
  self-custody wallet, no in-app trading (swap/deposit hand off to morm.one).

### E. Release
- Upload the AAB to **Internal testing** first (instant, up to 100 testers), then
  **Closed** → **Production**. New personal accounts may need ~14 days of closed
  testing with ≥12 testers before production is allowed — start internal testing
  early.

---

## Quick order of operations
1. **Android first** (cheaper/faster): Play Console $25 → internal testing AAB now →
   production after the testing requirement.
2. **iOS**: Apple Developer $99/yr → TestFlight (real-device) → passkey (AASA) →
   App Store review.
3. Keep signing keys safe & out of the repo: `morm-ext-key.pem` (extension, dev id),
   `morm-upload.jks` (Play upload key). Apple keys live in the Keychain/Xcode.

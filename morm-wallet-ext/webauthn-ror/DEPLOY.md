# Deploy: morm.one `/.well-known/webauthn` (passkey Related Origins)

Publish `webauthn.json` (this directory) so the browser serves it at **exactly**:

```
https://morm.one/.well-known/webauthn
```

Requirements:
- `Content-Type: application/json`
- 200, publicly readable, **no redirect** (a redirect makes Chrome reject it).
- Must also be reachable on `https://www.morm.one/.well-known/webauthn` if account.html
  runs on the `www` host (RP_ID `morm.one` covers both, but the file must sit on the
  origin the browser is on when it fetches ROR — serve it on both to be safe).

Verify after deploy:
```bash
curl -si https://morm.one/.well-known/webauthn | sed -n '1,10p'
# expect: HTTP/2 200 and content-type: application/json
```

## Per host

### Next.js (morm-dashboard / Vercel)
Place the file at `public/.well-known/webauthn` and force the JSON type via `vercel.json`:
```json
{
  "headers": [
    { "source": "/.well-known/webauthn",
      "headers": [{ "key": "Content-Type", "value": "application/json" }] }
  ]
}
```
(A file with no extension is otherwise served as octet-stream.)

### Cloudflare Pages
Put `webauthn.json` at `/.well-known/webauthn` in the output dir and add a `_headers` file:
```
/.well-known/webauthn
  Content-Type: application/json
```

### nginx (Mac Mini / zoku-style static host)
```nginx
location = /.well-known/webauthn {
    default_type application/json;
    alias /path/to/webauthn.json;
    add_header Content-Type application/json;
}
```

## After first Chrome Web Store publish
The store assigns a **different** extension ID than the dev ID. Add it to `origins`:
```json
{ "origins": [
    "chrome-extension://enmmpmpjbdplcglnncnkjbebehddbeka",  // dev / unpacked
    "chrome-extension://<STORE_ID>"                          // published build
] }
```
Redeploy. ROR allows up to 5 origins.

## Confirmed behavior (why this file is required)
Without it, `navigator.credentials.create/get({ rpId: "morm.one" })` from the
extension origin fails with: *"The relying party ID is not a registrable domain
suffix of, nor equal to the current domain... fetch the .well-known/webauthn
resource of the claimed RP ID failed."* That is the exact gate this file opens.

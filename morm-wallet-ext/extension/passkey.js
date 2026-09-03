// WebAuthn passkey + PRF ceremonies — identical parameters to account.html
// (RP_ID = morm.one, PRF_SALT = "morm-wallet-prf-v1"), so the SAME passkey
// yields the SAME PRF secret on both surfaces. Requires morm.one to publish
// /.well-known/webauthn listing this extension's origin (Related Origin
// Requests, Chrome 128+); otherwise the platform refuses rpId:"morm.one" from
// the chrome-extension:// origin.
import { RP_ID, PRF_SALT } from "./walletcore/index.js";

export function webauthnSupported() {
  return !!(globalThis.PublicKeyCredential && navigator.credentials?.create);
}

function rnd(n) {
  return crypto.getRandomValues(new Uint8Array(n));
}

// Create a new passkey bound to rpId=morm.one and evaluate PRF at creation.
// Returns { credId: Uint8Array, prf: Uint8Array(32) }. Falls back to a follow-up
// assertion if the authenticator didn't return PRF during create.
export async function createPasskey(displayName) {
  const userId = rnd(16);
  const name = displayName || ("morm-" + [...userId.slice(0, 4)].map((b) => b.toString(16).padStart(2, "0")).join(""));
  const cred = await navigator.credentials.create({
    publicKey: {
      rp: { id: RP_ID, name: "MORM" },
      user: { id: userId, name, displayName: name },
      challenge: rnd(32),
      pubKeyCredParams: [
        { type: "public-key", alg: -8 },   // Ed25519
        { type: "public-key", alg: -7 },   // ES256
        { type: "public-key", alg: -257 }, // RS256
      ],
      authenticatorSelection: { userVerification: "preferred", residentKey: "preferred" },
      timeout: 60000,
      extensions: { prf: { eval: { first: PRF_SALT } } },
    },
  });
  const credId = new Uint8Array(cred.rawId);
  const ext = cred.getClientExtensionResults?.();
  let prf = ext?.prf?.results?.first ? new Uint8Array(ext.prf.results.first) : null;
  if (!prf) prf = await passkeyPRF(credId); // some authenticators only expose PRF via get()
  if (!prf) throw new Error("このパスキー/認証器は PRF に対応していません");
  return { credId, prf };
}

// Ask the authenticator to evaluate PRF for an existing credential.
// Returns Uint8Array(32) or null if PRF unsupported.
export async function passkeyPRF(credId) {
  const assertion = await navigator.credentials.get({
    publicKey: {
      rpId: RP_ID,
      challenge: rnd(32),
      allowCredentials: [{ type: "public-key", id: credId }],
      userVerification: "preferred",
      timeout: 60000,
      extensions: { prf: { eval: { first: PRF_SALT } } },
    },
  });
  const ext = assertion.getClientExtensionResults?.();
  return ext?.prf?.results?.first ? new Uint8Array(ext.prf.results.first) : null;
}

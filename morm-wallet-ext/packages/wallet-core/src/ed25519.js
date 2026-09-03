// Ed25519 via WebCrypto (SubtleCrypto) — the same primitive the production
// account.html uses. Available in Chrome (extension service worker + pages) and
// Node 20+. Ed25519 is deterministic, so signatures match the Python reference
// (morm-l1 uses `cryptography`) byte-for-byte.

const subtle = globalThis.crypto?.subtle;
if (!subtle) throw new Error("WebCrypto SubtleCrypto unavailable");

// PKCS8 DER prefix for a raw 32-byte Ed25519 seed.
const PKCS8_PREFIX = hexToBytes("302e020100300506032b657004220420");
// SPKI DER prefix for a raw 32-byte Ed25519 public key.
const SPKI_PREFIX = hexToBytes("302a300506032b6570032100");

function hexToBytes(hex) {
  const clean = hex.length % 2 ? "0" + hex : hex;
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substr(i * 2, 2), 16);
  }
  return out;
}

export function bytesToHex(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += bytes[i].toString(16).padStart(2, "0");
  return s;
}

function concat(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

async function importPrivateFromSeed(seed) {
  if (!(seed instanceof Uint8Array) || seed.length !== 32) {
    throw new Error("seed must be a 32-byte Uint8Array");
  }
  return subtle.importKey("pkcs8", concat(PKCS8_PREFIX, seed), { name: "Ed25519" }, false, ["sign"]);
}

// Generate a fresh account: returns { seed, pubkey } as 32-byte Uint8Arrays.
export async function generateSeed() {
  const kp = await subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const jwk = await subtle.exportKey("jwk", kp.privateKey);
  const pub = new Uint8Array(await subtle.exportKey("raw", kp.publicKey));
  return { seed: b64uToBytes(jwk.d), pubkey: pub };
}

// Derive the 32-byte public key from a 32-byte seed.
export async function pubkeyFromSeed(seed) {
  const priv = await importPrivateFromSeed(seed);
  // WebCrypto has no private->public export, so round-trip through jwk.x.
  // importKey(pkcs8) yields a non-extractable key; re-import extractable to read x.
  const ext = await subtle.importKey("pkcs8", concat(PKCS8_PREFIX, seed), { name: "Ed25519" }, true, ["sign"]);
  const jwk = await subtle.exportKey("jwk", ext);
  void priv;
  return b64uToBytes(jwk.x);
}

// Sign a message (Uint8Array) with the seed; returns a 64-byte signature.
export async function sign(seed, message) {
  const priv = await importPrivateFromSeed(seed);
  const sig = await subtle.sign({ name: "Ed25519" }, priv, message);
  return new Uint8Array(sig);
}

// Verify a signature given a raw 32-byte public key.
export async function verify(pubkey, message, signature) {
  const pub = await subtle.importKey("spki", concat(SPKI_PREFIX, pubkey), { name: "Ed25519" }, false, ["verify"]);
  return subtle.verify({ name: "Ed25519" }, pub, signature, message);
}

// base64url <-> bytes (JWK uses base64url without padding).
function b64uToBytes(s) {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export { hexToBytes };

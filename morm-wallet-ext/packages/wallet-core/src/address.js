// MORM Chain address helpers — byte-for-byte compatible with
// morm-l1/morm_l1/crypto.py and morm-dashboard/app/lib/morm-address.js.
//   address = "m0r" + base32( BLAKE2b-256(pubkey)[-20:] )   (lowercase, 35 chars)
import { blake2b } from "./blake2b.js";
import { base32Encode } from "./base32.js";

export const ADDR_PREFIX = "m0r";
const M0R_RE = /^m0r[a-z2-7]{32}$/;

// Derive the m0r address from a raw 32-byte ed25519 public key (Uint8Array).
export function addressFromPubkey(pubkey) {
  if (!(pubkey instanceof Uint8Array) || pubkey.length !== 32) {
    throw new Error("pubkey must be a 32-byte Uint8Array");
  }
  const digest = blake2b(pubkey, 32); // BLAKE2b-256
  const raw20 = digest.subarray(12); // last 20 bytes
  return ADDR_PREFIX + base32Encode(raw20);
}

// Structural validity only (m0r + 32 base32 chars). NOTE: the format carries NO
// checksum, so a typo can yield a different-but-valid address. Callers MUST
// confirm the resolved recipient (e.g. via handle resolution) before sending.
export function isValidMormAddress(s) {
  return typeof s === "string" && M0R_RE.test(s);
}

export function isEvmAddress(s) {
  return typeof s === "string" && /^0x[0-9a-fA-F]{40}$/.test(s.trim());
}

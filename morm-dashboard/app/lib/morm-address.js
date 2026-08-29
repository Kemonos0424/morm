// MORM Chain address helpers — mirrors morm-l1/morm_l1/crypto.py exactly.
//   address = "m0r" + base32( BLAKE2b-256(pubkey)[-20:] ).lower()   (35 chars)
// Keys are ed25519 (32-byte seed / 32-byte pubkey). This module is the single
// server-side source of truth for validating a client-issued m0r address and
// proving the registrant holds the matching private key.
import crypto from 'crypto';
import { blake2b } from 'blakejs';

const ADDR_PREFIX = 'm0r';
const B32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; // RFC 4648

function base32(bytes) {
  let out = '', bits = 0, val = 0;
  for (const x of bytes) {
    val = (val << 8) | x; bits += 8;
    while (bits >= 5) { out += B32[(val >>> (bits - 5)) & 31]; bits -= 5; }
  }
  if (bits > 0) out += B32[(val << (5 - bits)) & 31];
  return out;
}

// Derive the m0r address from a raw 32-byte ed25519 public key.
export function addressFromPubkey(pubkey) {
  const buf = Buffer.isBuffer(pubkey) ? pubkey : Buffer.from(pubkey);
  const digest = Buffer.from(blake2b(buf, undefined, 32)); // BLAKE2b-256
  const raw20 = digest.subarray(12);                        // last 20 bytes
  return ADDR_PREFIX + base32(raw20).toLowerCase();
}

// m0r + 32 base32 chars (20 bytes * 8 / 5), lowercase alphabet a-z2-7.
export function isValidMormAddress(s) {
  return typeof s === 'string' && /^m0r[a-z2-7]{32}$/.test(s);
}

export function isHexPubkey(s) {
  return typeof s === 'string' && /^[0-9a-fA-F]{64}$/.test(s);
}

// Wrap a raw 32-byte ed25519 public key in SPKI DER so Node crypto can verify.
function pubKeyObjFromRaw(raw32) {
  const spki = Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), raw32]);
  return crypto.createPublicKey({ key: spki, format: 'der', type: 'spki' });
}

// Verify an ed25519 signature (hex) over `message` (utf-8 string) by `pubkeyHex`.
export function verifyEd25519(pubkeyHex, message, sigHex) {
  try {
    const pub = pubKeyObjFromRaw(Buffer.from(pubkeyHex, 'hex'));
    return crypto.verify(null, Buffer.from(message, 'utf8'), pub, Buffer.from(sigHex, 'hex'));
  } catch {
    return false;
  }
}

// Canonical message a client signs to prove ownership at registration time.
export function registerMessage(address) {
  return `MORM-REGISTER:v1:${address}`;
}

// Canonical message an agent signs to claim a lane earn (view/serve/etc.).
// The (address, kind, ref) triple is also the server-side dedup key, so a
// captured signature is single-use — replay is rejected by the UNIQUE index.
export function laneEarnMessage(address, kind, ref) {
  return `MORM-LANE-EARN:v1:${address}:${kind}:${ref}`;
}

// Canonical message a serving node/creator signs to claim an ad event
// (impression/click). (campaign, earner, kind, ref) is the dedup key.
export function adEventMessage(campaignId, earner, kind, ref) {
  return `MORM-AD-EVENT:v1:${campaignId}:${earner}:${kind}:${ref}`;
}

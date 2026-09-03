// MORM L1 transaction building + signing. Mirrors morm-l1/morm_l1/tx.py.
//   signing pre-image = canonical({kind, sender(hex), nonce, payload})
//   wire              = {kind, sender(hex), nonce, payload, signature(hex)}
import { canonicalBytes, canonicalStringify } from "./canonical.js";
import { sign as edSign, bytesToHex } from "./ed25519.js";
import { isValidMormAddress } from "./address.js";

export const TxKind = { TRANSFER: 6, BRIDGE_BURN: 21 };

// Build the unsigned canonical body for a TRANSFER. `amount` is coerced to
// BigInt so large balances (>2^53) sign correctly.
export function buildTransfer({ senderPubkeyHex, nonce, to, amount }) {
  if (!/^[0-9a-fA-F]{64}$/.test(senderPubkeyHex)) throw new Error("senderPubkeyHex must be 64 hex chars");
  if (!Number.isInteger(nonce) || nonce < 0) throw new Error("nonce must be a non-negative integer");
  if (!isValidMormAddress(to)) throw new Error("`to` must be a valid m0r address");
  const amt = toBigIntPositive(amount);
  return {
    kind: TxKind.TRANSFER,
    sender: senderPubkeyHex.toLowerCase(),
    nonce,
    payload: { to, amount: amt },
  };
}

// Build an unsigned BRIDGE_BURN (kind 21): burn native MORM on L1 so the
// relayer mints wMORM on Base for `evmRecipient`. payload keys are sorted by the
// canonical encoder, so field order here is irrelevant to the signature.
export function buildBridgeBurn({ senderPubkeyHex, nonce, amount, evmRecipient, token = "MORM" }) {
  if (!/^[0-9a-fA-F]{64}$/.test(senderPubkeyHex)) throw new Error("senderPubkeyHex must be 64 hex chars");
  if (!Number.isInteger(nonce) || nonce < 0) throw new Error("nonce must be a non-negative integer");
  if (!/^0x[0-9a-fA-F]{40}$/.test(String(evmRecipient))) throw new Error("evmRecipient must be a 0x 20-byte address");
  if (token !== "MORM") throw new Error('only token "MORM" is supported for forward bridge');
  const amt = toBigIntPositive(amount);
  return {
    kind: TxKind.BRIDGE_BURN,
    sender: senderPubkeyHex.toLowerCase(),
    nonce,
    payload: { amount: amt, evm_recipient: evmRecipient, token },
  };
}

function toBigIntPositive(x) {
  let v;
  if (typeof x === "bigint") v = x;
  else if (typeof x === "number") {
    if (!Number.isInteger(x)) throw new Error("amount must be an integer");
    v = BigInt(x);
  } else if (typeof x === "string" && /^[0-9]+$/.test(x)) v = BigInt(x);
  else throw new Error("amount must be a positive integer (BigInt, integer, or digit string)");
  if (v <= 0n) throw new Error("amount must be positive");
  return v;
}

// The exact bytes the L1 verifies the signature against.
export function signingBytes(body) {
  return canonicalBytes({
    kind: body.kind,
    sender: body.sender,
    nonce: body.nonce,
    payload: body.payload,
  });
}

// Sign an unsigned body with the seed; returns the full wire tx object
// (payload.amount stays BigInt — serialize with `serializeTx` for the wire).
export async function signTx(body, seed) {
  const sig = await edSign(seed, signingBytes(body));
  return { ...body, signature: bytesToHex(sig) };
}

// Serialize a (signed) tx to the JSON string to POST to /tx. Uses the
// BigInt-aware canonical serializer so large amounts are emitted as JSON
// numbers without precision loss.
export function serializeTx(tx) {
  return canonicalStringify(tx);
}

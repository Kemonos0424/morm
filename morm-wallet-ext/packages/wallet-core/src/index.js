// @morm/wallet-core — framework-agnostic MORM wallet primitives.
// Byte-for-byte compatible with morm-l1 (Python) and morm.one/account.html.
export { ADDR_PREFIX, addressFromPubkey, isValidMormAddress, isEvmAddress } from "./address.js";
export { base32Encode, base32Decode } from "./base32.js";
export { blake2b } from "./blake2b.js";
export { canonicalStringify, canonicalBytes } from "./canonical.js";
export { generateSeed, pubkeyFromSeed, sign, verify, bytesToHex, hexToBytes } from "./ed25519.js";
export { TxKind, buildTransfer, buildBridgeBurn, signingBytes, signTx, serializeTx } from "./tx.js";
export { seedToRecovery, recoveryToSeed } from "./recovery.js";
export {
  PRF_SALT, RP_ID,
  aesKeyFromPassword, aesKeyFromPRF,
  encryptSeed, decryptSeed, newSalt,
  bytesToB64u, b64uToBytes,
} from "./vault.js";
export { getAccountState, submitTransfer, submitBridgeBurn, resolveHandle, getNodes } from "./rpc.js";
export { mormToBaseUnits, formatBaseUnits } from "./units.js";

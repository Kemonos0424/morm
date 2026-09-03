// MORM dashboard API client (api.morm.one). The extension calls these with a
// PINNED base URL (never page-supplied) and reaches the host via manifest
// host_permissions, so it isn't subject to the server's CORS allowlist.
import { serializeTx } from "./tx.js";

async function getJson(url, opts) {
  const res = await fetch(url, { cache: "no-store", ...opts });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

const trim = (b) => b.replace(/\/$/, "");

// GET {api}/api/wallet/account/{address}
// -> { address, registered, handle, evmAddress, baseUnitsPerMorm, chain:{ wired, balance, nonce, balanceMorm, ... } }
export async function getAccountState(apiBase, address) {
  const { ok, status, data } = await getJson(`${trim(apiBase)}/api/wallet/account/${encodeURIComponent(address)}`);
  if (!ok) throw new Error(data.error || `account HTTP ${status}`);
  return data;
}

// GET {nodeBase}/api/nodes/by-reward/{address}
//   -> { address, baseUnitsPerMorm, nodes:[...], emissions:[...] }
// Read-only, secret-free, scoped to the node reward address (nodes.morm_address).
// Node rewards are push-based, so there is no claim here. `nodeBase` is
// node.morm.one (separate app/DB from api.morm.one).
export async function getNodes(nodeBase, address) {
  const { ok, status, data } = await getJson(`${trim(nodeBase)}/api/nodes/by-reward/${encodeURIComponent(address)}`);
  if (status === 404) return { unavailable: true, nodes: [], emissions: [] };
  if (!ok) throw new Error(data.error || `nodes HTTP ${status}`);
  return data;
}

// GET {api}/api/wallet/resolve/{handle} -> { found:true, handle, address } | { found:false } (404)
export async function resolveHandle(apiBase, handle) {
  const h = String(handle).replace(/^@/, "").toLowerCase().trim();
  const { ok, status, data } = await getJson(`${trim(apiBase)}/api/wallet/resolve/${encodeURIComponent(h)}`);
  if (status === 404) return { found: false };
  if (!ok) throw new Error(data.error || `resolve HTTP ${status}`);
  return data;
}

// POST {api}/api/wallet/submit-tx with a signed TRANSFER (kind 6).
export async function submitTransfer(apiBase, signedTx) {
  const { ok, status, data } = await getJson(`${trim(apiBase)}/api/wallet/submit-tx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: serializeTx(signedTx),
  });
  if (!ok || !data.ok) throw new Error(data.error || `submit HTTP ${status}`);
  return data; // { ok, txHash, mempool }
}

// POST {api}/api/wallet/bridge-burn with a signed BRIDGE_BURN (kind 21).
export async function submitBridgeBurn(apiBase, signedTx) {
  const { ok, status, data } = await getJson(`${trim(apiBase)}/api/wallet/bridge-burn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: serializeTx(signedTx),
  });
  if (!ok || !data.ok) throw new Error(data.error || `bridge HTTP ${status}`);
  return data;
}

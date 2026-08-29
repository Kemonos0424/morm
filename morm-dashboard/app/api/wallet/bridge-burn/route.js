import { NextResponse } from 'next/server';
import { isHexPubkey, addressFromPubkey } from '@/app/lib/morm-address';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';
import { checkBurn, recordBurn } from '@/app/lib/bridge-valve';

export const dynamic = 'force-dynamic';

// Relay a client-signed BRIDGE_BURN (kind=21) to the MORM L1. This is the
// "forward" bridge direction: burn native MORM on L1 so the off-chain relayer
// mints wMORM on Base for `evm_recipient`. The tx is signed in the browser with
// the user's own key (never leaves the device); this route only validates the
// shape and relays it. Kept separate from submit-tx (which is kind-6 only) so
// each public proxy accepts exactly one tx kind.
const TX_KIND_BRIDGE_BURN = 21;
// The deployed relayer runs EXPORT_TOKEN="MORM": only token=="MORM" burns the
// user's native balance (state.py _tx_bridge_burn). Any other token would
// require an L1 ERC-20-mirror balance native users don't have — reject it.
const ALLOWED_TOKEN = 'MORM';

function cors(origin) {
  const allowed = [
    'https://morm.one', 'https://www.morm.one',
    'http://localhost:8791', 'http://localhost:3000', 'http://127.0.0.1:8791',
  ];
  const allow = allowed.includes(origin) ? origin : 'https://morm.one';
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

export async function OPTIONS(request) {
  return new Response(null, { status: 204, headers: cors(request.headers.get('origin')) });
}

export async function POST(request) {
  const headers = cors(request.headers.get('origin'));
  try {
    const rpc = (process.env.MORM_L1_RPC_URL || '').replace(/\/$/, '');
    if (!rpc) return NextResponse.json({ error: 'L1 not configured' }, { status: 503, headers });

    const tx = await request.json().catch(() => null);
    if (!tx || typeof tx !== 'object') {
      return NextResponse.json({ error: 'tx body required' }, { status: 400, headers });
    }
    if (Number(tx.kind) !== TX_KIND_BRIDGE_BURN) {
      return NextResponse.json({ error: 'only BRIDGE_BURN (kind 21) allowed here' }, { status: 400, headers });
    }
    if (!isHexPubkey(tx.sender)) {
      return NextResponse.json({ error: 'sender must be 32-byte pubkey hex' }, { status: 400, headers });
    }
    if (!Number.isInteger(tx.nonce) || tx.nonce < 0) {
      return NextResponse.json({ error: 'nonce must be a non-negative integer' }, { status: 400, headers });
    }
    const p = tx.payload || {};
    if (!Number.isInteger(p.amount) || p.amount <= 0) {
      return NextResponse.json({ error: 'payload.amount must be a positive integer' }, { status: 400, headers });
    }
    if (typeof p.evm_recipient !== 'string' || !/^0x[0-9a-fA-F]{40}$/.test(p.evm_recipient)) {
      return NextResponse.json({ error: 'payload.evm_recipient must be a 0x-prefixed 20-byte address' }, { status: 400, headers });
    }
    const token = p.token || ALLOWED_TOKEN;
    if (token !== ALLOWED_TOKEN) {
      return NextResponse.json({ error: `only token="${ALLOWED_TOKEN}" is supported for forward` }, { status: 400, headers });
    }
    if (typeof tx.signature !== 'string' || !/^[0-9a-fA-F]+$/.test(tx.signature)) {
      return NextResponse.json({ error: 'signature must be hex' }, { status: 400, headers });
    }
    let signer;
    try { signer = addressFromPubkey(Buffer.from(tx.sender, 'hex')); } catch {
      return NextResponse.json({ error: 'bad sender pubkey' }, { status: 400, headers });
    }

    // Cash-out valve (Phase 2-③): throttle the forward bridge to protect the
    // thin price reference. Flag-gated (BRIDGE_VALVE=on); bypasses otherwise, so
    // default behavior is unchanged. p.amount is in L1 base units.
    let gate;
    try {
      gate = await checkBurn({ fromAddr: signer, amountUnits: p.amount });
    } catch (e) {
      gate = { ok: true, bypass: true, valveError: e.message }; // never hard-fail on a valve bug
    }
    if (!gate.ok) {
      return NextResponse.json({ error: gate.reason, valve: gate }, { status: gate.code || 429, headers });
    }

    // Forward the payload EXACTLY as it was signed. The L1 recomputes the
    // canonical signing pre-image from this dict and verifies the Ed25519
    // signature + native balance; reordering values here would break it.
    const res = await fetch(`${rpc}/tx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: TX_KIND_BRIDGE_BURN,
        sender: tx.sender,
        nonce: tx.nonce,
        payload: { amount: p.amount, evm_recipient: p.evm_recipient, token },
        signature: tx.signature,
      }),
      cache: 'no-store',
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      return NextResponse.json({ error: data.error || `L1 rejected (${res.status})` }, { status: 400, headers });
    }
    // Index for history (from = signer address, to = the EVM recipient) and
    // record the burn against the valve's 24h accounting.
    try {
      await ensureWalletSchema();
      await recordTx({ txHash: data.tx_hash, from: signer, to: p.evm_recipient, amount: p.amount, kind: 'bridge-burn' });
    } catch { /* non-critical */ }
    if (!gate.bypass) {
      await recordBurn({ fromAddr: signer, amountUnits: p.amount, usd: gate.usd || 0, txHash: data.tx_hash });
    }
    return NextResponse.json({ ok: true, txHash: data.tx_hash, mempool: data.mempool_size }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

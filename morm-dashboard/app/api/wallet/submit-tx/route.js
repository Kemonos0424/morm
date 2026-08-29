import { NextResponse } from 'next/server';
import { isValidMormAddress, isHexPubkey, addressFromPubkey } from '@/app/lib/morm-address';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';

export const dynamic = 'force-dynamic';

// Forward a client-signed TRANSFER tx to the MORM L1. The tx is signed in the
// browser with the user's own key (the private key never leaves the device);
// this route only relays it to the L1 RPC and returns the result. Restricted to
// kind=6 (TRANSFER) so the public proxy can't be used for other tx kinds.
const TX_KIND_TRANSFER = 6;

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
    if (Number(tx.kind) !== TX_KIND_TRANSFER) {
      return NextResponse.json({ error: 'only TRANSFER (kind 6) allowed here' }, { status: 400, headers });
    }
    if (!isHexPubkey(tx.sender)) {
      return NextResponse.json({ error: 'sender must be 32-byte pubkey hex' }, { status: 400, headers });
    }
    if (!Number.isInteger(tx.nonce) || tx.nonce < 0) {
      return NextResponse.json({ error: 'nonce must be a non-negative integer' }, { status: 400, headers });
    }
    const p = tx.payload || {};
    if (!isValidMormAddress(p.to)) {
      return NextResponse.json({ error: 'payload.to must be a valid m0r address' }, { status: 400, headers });
    }
    if (!Number.isInteger(p.amount) || p.amount <= 0) {
      return NextResponse.json({ error: 'payload.amount must be a positive integer' }, { status: 400, headers });
    }
    if (typeof tx.signature !== 'string' || !/^[0-9a-fA-F]+$/.test(tx.signature)) {
      return NextResponse.json({ error: 'signature must be hex' }, { status: 400, headers });
    }
    // sanity: sender pubkey must correspond to a real m0r address (not enforced
    // to equal any particular account — the L1 verifies the signature + balance).
    try { addressFromPubkey(Buffer.from(tx.sender, 'hex')); } catch {
      return NextResponse.json({ error: 'bad sender pubkey' }, { status: 400, headers });
    }

    const res = await fetch(`${rpc}/tx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: TX_KIND_TRANSFER,
        sender: tx.sender,
        nonce: tx.nonce,
        payload: { to: p.to, amount: p.amount },
        signature: tx.signature,
      }),
      cache: 'no-store',
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      return NextResponse.json({ error: data.error || `L1 rejected (${res.status})` }, { status: 400, headers });
    }
    // Index for history (from = address derived from the signer pubkey).
    try {
      await ensureWalletSchema();
      const from = addressFromPubkey(Buffer.from(tx.sender, 'hex'));
      await recordTx({ txHash: data.tx_hash, from, to: p.to, amount: p.amount, kind: 'transfer' });
    } catch { /* non-critical */ }
    return NextResponse.json({ ok: true, txHash: data.tx_hash, mempool: data.mempool_size }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

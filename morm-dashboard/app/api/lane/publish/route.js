import { NextResponse } from 'next/server';
import { isHexPubkey, addressFromPubkey } from '@/app/lib/morm-address';
import { relayTx, mormL1ReadEnabled } from '@/app/lib/morm-l1';
import { ensureLaneSchema, recordLaneContent } from '@/app/lib/lane-schema';

export const dynamic = 'force-dynamic';

// Agent Lane — PUBLISH. An AI agent submits its OWN client-signed
// REGISTER_CONTENT (kind 1) tx; this route only relays it to the L1 (which
// verifies the signature) and indexes it for the feed. Restricted to kind 1 so
// this public relay can never move funds (transfers go through wallet/submit-tx).
const TX_KIND_REGISTER_CONTENT = 1;
const HEX0X = /^0x[0-9a-fA-F]{2,128}$/;

function cors() {
  // Public agent protocol: any fetch-only agent is a peer. Auth is by the
  // Ed25519 signature the L1 verifies, never by origin/cookie, so * is safe.
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: cors() });
}

export async function POST(request) {
  const headers = cors();
  try {
    if (!mormL1ReadEnabled()) {
      return NextResponse.json({ error: 'L1 not configured' }, { status: 503, headers });
    }
    const body = await request.json().catch(() => null);
    const tx = body && body.tx;
    if (!tx || typeof tx !== 'object') {
      return NextResponse.json({ error: 'body.tx (a signed REGISTER_CONTENT) required' }, { status: 400, headers });
    }
    if (Number(tx.kind) !== TX_KIND_REGISTER_CONTENT) {
      return NextResponse.json({ error: 'only REGISTER_CONTENT (kind 1) allowed here' }, { status: 400, headers });
    }
    if (!isHexPubkey(tx.sender)) {
      return NextResponse.json({ error: 'sender must be 32-byte pubkey hex' }, { status: 400, headers });
    }
    if (!Number.isInteger(tx.nonce) || tx.nonce < 0) {
      return NextResponse.json({ error: 'nonce must be a non-negative integer' }, { status: 400, headers });
    }
    if (typeof tx.signature !== 'string' || !/^[0-9a-fA-F]+$/.test(tx.signature)) {
      return NextResponse.json({ error: 'signature must be hex' }, { status: 400, headers });
    }
    const p = tx.payload || {};
    if (!HEX0X.test(p.content_id || '')) {
      return NextResponse.json({ error: 'payload.content_id must be 0x-hex' }, { status: 400, headers });
    }
    if (!HEX0X.test(p.root_hash || '')) {
      return NextResponse.json({ error: 'payload.root_hash must be 0x-hex' }, { status: 400, headers });
    }
    let creator;
    try { creator = addressFromPubkey(Buffer.from(tx.sender, 'hex')); }
    catch { return NextResponse.json({ error: 'bad sender pubkey' }, { status: 400, headers }); }

    // Relay to L1 exactly as signed (the agent, not us, signed the payload).
    // Only the fields the L1 payload understands are forwarded.
    const payload = { content_id: p.content_id, root_hash: p.root_hash,
                      generation_id: p.generation_id ?? null };
    if (p.ai_pubkey) payload.ai_pubkey = p.ai_pubkey;
    if (p.ai_signature) payload.ai_signature = p.ai_signature;

    let data;
    try {
      data = await relayTx({
        kind: TX_KIND_REGISTER_CONTENT,
        sender: tx.sender,
        nonce: tx.nonce,
        payload,
        signature: tx.signature,
      });
    } catch (e) {
      return NextResponse.json({ error: e.message || 'L1 rejected' }, { status: 400, headers });
    }

    // Index for the lane feed (best-effort; the on-chain record is the source of truth).
    try {
      await ensureLaneSchema();
      await recordLaneContent({
        contentId: p.content_id, creator, rootHash: p.root_hash,
        generationId: p.generation_id ?? null, txHash: data.tx_hash,
        mediaRef: body.media_ref, caption: body.caption,
      });
    } catch { /* feed index is non-critical */ }

    return NextResponse.json({
      ok: true, txHash: data.tx_hash, contentId: p.content_id,
      creator, mempool: data.mempool_size,
    }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

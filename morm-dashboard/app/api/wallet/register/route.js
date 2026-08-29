import { NextResponse } from 'next/server';
import crypto from 'crypto';
import { dbGet, dbRun } from '@/app/lib/db';
import {
  addressFromPubkey, isValidMormAddress, isHexPubkey,
  verifyEd25519, registerMessage,
} from '@/app/lib/morm-address';
import { mormL1Enabled, transferMorm } from '@/app/lib/morm-l1';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';

export const dynamic = 'force-dynamic';

const FAUCET_MORM = Number(process.env.MORM_FAUCET_AMOUNT || 1); // initial drip to materialize the account
const HANDLE_RE = /^[a-z0-9_]{3,20}$/;

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
    await ensureWalletSchema();
    const body = await request.json().catch(() => ({}));
    let { address, pubkey, sig, handle } = body;

    // ── validate identity ─────────────────────────────────────────────
    if (!isValidMormAddress(address)) {
      return NextResponse.json({ error: 'invalid m0r address' }, { status: 400, headers });
    }
    if (!isHexPubkey(pubkey)) {
      return NextResponse.json({ error: 'pubkey must be 64 hex chars' }, { status: 400, headers });
    }
    // The address MUST be the one derived from this pubkey (no spoofing).
    if (addressFromPubkey(Buffer.from(pubkey, 'hex')) !== address) {
      return NextResponse.json({ error: 'address does not match pubkey' }, { status: 400, headers });
    }
    // Proof of key possession: sig over the canonical register message.
    if (typeof sig !== 'string' || !verifyEd25519(pubkey, registerMessage(address), sig)) {
      return NextResponse.json({ error: 'invalid ownership signature' }, { status: 401, headers });
    }

    // ── optional handle ───────────────────────────────────────────────
    if (handle != null && handle !== '') {
      handle = String(handle).toLowerCase().trim();
      if (!HANDLE_RE.test(handle)) {
        return NextResponse.json({ error: 'handle must be 3-20 chars: a-z 0-9 _' }, { status: 400, headers });
      }
      const taken = await dbGet('SELECT address FROM morm_accounts WHERE handle = ?', [handle]);
      if (taken && taken.address !== address) {
        return NextResponse.json({ error: 'handle already taken' }, { status: 409, headers });
      }
    } else {
      handle = null;
    }

    // ── idempotent: already registered → return it ────────────────────
    const existing = await dbGet('SELECT * FROM morm_accounts WHERE address = ?', [address]);
    if (existing) {
      return NextResponse.json({
        ok: true, address, handle: existing.handle,
        faucet: { status: existing.faucet_status, tx: existing.faucet_tx },
        alreadyRegistered: true,
      }, { headers });
    }

    // ── faucet: materialize the account on the real L1 (best effort) ──
    let faucetTx = null, faucetStatus = 'pending';
    if (mormL1Enabled()) {
      try {
        const r = await transferMorm({ to: address, mormAmount: FAUCET_MORM });
        faucetTx = r.txHash; faucetStatus = 'sent';
        await recordTx({ txHash: r.txHash, from: process.env.MORM_TREASURY_ADDRESS, to: address, amount: FAUCET_MORM, kind: 'faucet' });
      } catch (e) {
        faucetStatus = 'failed';
        console.error('[wallet/register] faucet failed:', e.message);
      }
    } else {
      faucetStatus = 'simulated'; // chain not wired in this env; address is still valid
    }

    const ipHash = crypto
      .createHash('sha256')
      .update((request.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'unknown')
      .digest('hex').slice(0, 16);

    await dbRun(
      `INSERT INTO morm_accounts (address, handle, pubkey, passkey_cred_id, faucet_tx, faucet_status, ip_hash)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [address, handle, pubkey, body.credId || null, faucetTx, faucetStatus, ipHash]
    );

    return NextResponse.json({
      ok: true, address, handle,
      faucet: { status: faucetStatus, tx: faucetTx, amount: FAUCET_MORM },
    }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

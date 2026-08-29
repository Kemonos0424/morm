import { NextResponse } from 'next/server';
import { dbGet, dbRun } from '@/app/lib/db';
import { isValidMormAddress } from '@/app/lib/morm-address';
import { mormL1Enabled, transferMorm } from '@/app/lib/morm-l1';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';

export const dynamic = 'force-dynamic';

// One-time test faucet: tops a registered account up with test MORM so users can
// try transfers. Guarded by a per-account `faucet_claimed` flag so it can't be
// drained. Amount is generous for testnet play; treasury holds 1e18.
const CLAIM_MORM = Number(process.env.MORM_FAUCET_CLAIM || 100);

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
    const { address } = await request.json().catch(() => ({}));
    if (!isValidMormAddress(address)) {
      return NextResponse.json({ error: 'invalid m0r address' }, { status: 400, headers });
    }
    const row = await dbGet('SELECT address, faucet_claimed FROM morm_accounts WHERE address = ?', [address]);
    if (!row) return NextResponse.json({ error: 'account not registered' }, { status: 404, headers });
    if (Number(row.faucet_claimed) === 1) {
      return NextResponse.json({ error: 'test faucet already claimed for this account' }, { status: 409, headers });
    }
    if (!mormL1Enabled()) {
      return NextResponse.json({ error: 'L1 faucet not available' }, { status: 503, headers });
    }

    const r = await transferMorm({ to: address, mormAmount: CLAIM_MORM });
    await recordTx({ txHash: r.txHash, from: process.env.MORM_TREASURY_ADDRESS, to: address, amount: CLAIM_MORM, kind: 'faucet' });
    await dbRun(
      `UPDATE morm_accounts SET faucet_claimed = 1, faucet_tx = ?, faucet_status = 'sent', updated_at = datetime('now') WHERE address = ?`,
      [r.txHash, address]
    );
    return NextResponse.json({ ok: true, address, amount: CLAIM_MORM, tx: r.txHash }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

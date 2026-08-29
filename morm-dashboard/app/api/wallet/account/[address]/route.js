import { NextResponse } from 'next/server';
import { dbGet } from '@/app/lib/db';
import { isValidMormAddress } from '@/app/lib/morm-address';
import { getL1Account, mormL1ReadEnabled } from '@/app/lib/morm-l1';
import { unitsToMorm, baseUnitsPerMorm } from '@/app/lib/morm-units';
import { ensureWalletSchema } from '@/app/lib/wallet-schema';

export const dynamic = 'force-dynamic';

function cors(origin) {
  const allowed = [
    'https://morm.one', 'https://www.morm.one',
    'http://localhost:8791', 'http://localhost:3000', 'http://127.0.0.1:8791',
  ];
  const allow = allowed.includes(origin) ? origin : 'https://morm.one';
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'GET,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
  };
}

export async function OPTIONS(request) {
  return new Response(null, { status: 204, headers: cors(request.headers.get('origin')) });
}

export async function GET(request, { params }) {
  const headers = cors(request.headers.get('origin'));
  try {
    await ensureWalletSchema();
    const address = params.address;
    if (!isValidMormAddress(address)) {
      return NextResponse.json({ error: 'invalid m0r address' }, { status: 400, headers });
    }

    const row = await dbGet('SELECT address, handle, faucet_status, faucet_tx, created_at FROM morm_accounts WHERE address = ?', [address]);

    // On-chain state (balance / nonce). null when the L1 RPC isn't wired.
    const l1 = await getL1Account(address);

    return NextResponse.json({
      address,
      registered: Boolean(row),
      handle: row?.handle || null,
      faucet: row ? { status: row.faucet_status, tx: row.faucet_tx } : null,
      createdAt: row?.created_at || null,
      baseUnitsPerMorm: baseUnitsPerMorm(),
      chain: {
        wired: mormL1ReadEnabled(),
        // raw integer base units (unchanged for compatibility) …
        balance: l1 ? Number(l1.balance || 0) : null,
        nonce: l1 ? Number(l1.nonce || 0) : null,
        stake: l1 ? Number(l1.stake || 0) : null,
        locked: l1 ? Number(l1.locked || 0) : null,
        // … plus MORM-denominated values via the single unit converter.
        balanceMorm: l1 ? unitsToMorm(l1.balance || 0) : null,
        stakeMorm: l1 ? unitsToMorm(l1.stake || 0) : null,
        lockedMorm: l1 ? unitsToMorm(l1.locked || 0) : null,
      },
    }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

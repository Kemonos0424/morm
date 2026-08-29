import { NextResponse } from 'next/server';
import { dbAll, dbGet } from '@/app/lib/db';
import { isValidMormAddress } from '@/app/lib/morm-address';
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

// Transaction history for an address (txs relayed through the dashboard:
// faucet in, transfers in/out). Newest first. Handles resolved when known.
export async function GET(request, { params }) {
  const headers = cors(request.headers.get('origin'));
  try {
    await ensureWalletSchema();
    const address = params.address;
    if (!isValidMormAddress(address)) {
      return NextResponse.json({ error: 'invalid m0r address' }, { status: 400, headers });
    }
    const rows = await dbAll(
      `SELECT tx_hash, from_addr, to_addr, amount, kind, created_at
         FROM morm_txs WHERE from_addr = ? OR to_addr = ?
        ORDER BY id DESC LIMIT 50`,
      [address, address]
    );
    const items = rows.map((r) => ({
      txHash: r.tx_hash,
      direction: r.to_addr === address ? 'in' : 'out',
      counterparty: r.to_addr === address ? r.from_addr : r.to_addr,
      amount: Number(r.amount) || 0,
      kind: r.kind,
      at: r.created_at,
    }));
    return NextResponse.json({ address, items }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

import { NextResponse } from 'next/server';
import { dbGet } from '@/app/lib/db';
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

// Resolve a public handle (@name) to its m0r address.
export async function GET(request, { params }) {
  const headers = cors(request.headers.get('origin'));
  try {
    await ensureWalletSchema();
    let handle = String(params.handle || '').toLowerCase().replace(/^@/, '').trim();
    if (!/^[a-z0-9_]{3,20}$/.test(handle)) {
      return NextResponse.json({ error: 'invalid handle' }, { status: 400, headers });
    }
    const row = await dbGet('SELECT address, handle FROM morm_accounts WHERE handle = ?', [handle]);
    if (!row) return NextResponse.json({ found: false }, { status: 404, headers });
    return NextResponse.json({ found: true, handle: row.handle, address: row.address }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

import { NextResponse } from 'next/server';
import { dbGet, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';
export async function POST(request) {
  const { address } = await request.json();
  if (!address) return NextResponse.json({ error: 'address required' }, { status: 400 });

  const existing = await dbGet('SELECT * FROM wallets WHERE address = ?', [address.toLowerCase()]);
  if (!existing) {
    await dbRun('INSERT INTO wallets (address) VALUES (?)', [address.toLowerCase()]);
  }

  const res = NextResponse.json({ success: true });
  res.cookies.set('wallet_address', address.toLowerCase(), { path: '/', maxAge: 60 * 60 * 24 * 30 });
  return res;
}

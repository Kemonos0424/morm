import { NextResponse } from 'next/server';
import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  const wallets = await dbAll('SELECT * FROM wallets ORDER BY created_at DESC');
  return NextResponse.json({ wallets });
}

import { NextResponse } from 'next/server';
import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const address = searchParams.get('address');
  if (!address) return NextResponse.json({ rewards: [] });

  const rewards = await dbAll(`
    SELECT ws.*, n.name as node_name
    FROM weekly_snapshots ws
    JOIN nodes n ON ws.node_id = n.id
    WHERE LOWER(ws.wallet_address) = LOWER(?)
    ORDER BY ws.created_at DESC
  `, [address]);

  return NextResponse.json({ rewards });
}

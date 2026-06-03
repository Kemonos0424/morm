import { NextResponse } from 'next/server';
import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address');
    if (!address) return NextResponse.json({ nodes: [] });

    const nodes = await dbAll(`
      SELECT n.id, n.name, n.morm_balance, n.morm_pending, n.morm_spent, n.task_score
      FROM nodes n
      LEFT JOIN wallets w ON n.id = w.node_id
      WHERE LOWER(n.wallet_address) = LOWER(?) OR LOWER(w.address) = LOWER(?)
    `, [address, address]);

    return NextResponse.json({ nodes });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

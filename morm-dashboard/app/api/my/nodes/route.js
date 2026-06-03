import { NextResponse } from 'next/server';
import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address');
    if (!address) return NextResponse.json({ nodes: [], connections: [] });

    // Search by wallet_address in nodes table OR wallets table
    const nodes = await dbAll(`
      SELECT DISTINCT n.* FROM nodes n
      LEFT JOIN wallets w ON n.id = w.node_id
      WHERE LOWER(n.wallet_address) = LOWER(?) OR LOWER(w.address) = LOWER(?)
    `, [address, address]);

    // Get connections for these nodes
    const nodeIds = nodes.map(n => n.id);
    let connections = [];
    if (nodeIds.length > 0) {
      const placeholders = nodeIds.map(() => '?').join(',');
      connections = await dbAll(`SELECT * FROM connections WHERE node_id IN (${placeholders})`, nodeIds);
    }

    return NextResponse.json({ nodes, connections });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

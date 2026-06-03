import { NextResponse } from 'next/server';
import { dbAll, dbRun, dbGet } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

function maskData(dataStr) {
  try {
    const obj = JSON.parse(dataStr);
    const masked = {};
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v === 'string' && v.length > 4) {
        masked[k] = v.substring(0, 4) + '****';
      } else {
        masked[k] = '****';
      }
    }
    return JSON.stringify(masked);
  } catch {
    return '****';
  }
}

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const address = searchParams.get('address');
    if (!address) return NextResponse.json({ credentials: [] });

    const credentials = await dbAll(`
      SELECT c.* FROM credentials c
      JOIN nodes n ON c.node_id = n.id
      LEFT JOIN wallets w ON n.id = w.node_id
      WHERE LOWER(n.wallet_address) = LOWER(?) OR LOWER(w.address) = LOWER(?)
      ORDER BY c.created_at DESC
    `, [address, address]);

    const masked = credentials.map(cr => ({
      ...cr,
      data: maskData(cr.data)
    }));

    return NextResponse.json({ credentials: masked });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const { node_id, service, credential_type, label, data } = await request.json();
    if (!node_id || !service || !data) {
      return NextResponse.json({ error: 'node_id, service, data are required' }, { status: 400 });
    }

    await dbRun(`
      INSERT INTO credentials (node_id, service, credential_type, label, data, created_at)
      VALUES (?, ?, ?, ?, ?, datetime('now'))
    `, [node_id, service, credential_type || service, label || service, typeof data === 'string' ? data : JSON.stringify(data)]);

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(request) {
  try {
    const { id } = await request.json();
    if (!id) return NextResponse.json({ error: 'id is required' }, { status: 400 });

    await dbRun('DELETE FROM credentials WHERE id = ?', [id]);
    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

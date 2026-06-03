import { NextResponse } from 'next/server';
import { dbAll, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const nodes = await dbAll('SELECT * FROM nodes ORDER BY total_score DESC');
    return NextResponse.json(nodes);
  } catch (err) {
    return NextResponse.json({ error: err.message, stack: err.stack }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { name, ssh_host, ssh_port, ssh_user, ssh_pass } = body;
    if (!name) return NextResponse.json({ error: 'name required' }, { status: 400 });
    const id = name.toLowerCase().replace(/[^a-z0-9]/g, '_');
    await dbRun(
      `INSERT INTO nodes (id, name, ssh_host, ssh_port, ssh_user, ssh_pass, status) VALUES (?, ?, ?, ?, ?, ?, 'offline')`,
      [id, name, ssh_host || null, ssh_port || 22, ssh_user || null, ssh_pass || null]
    );
    return NextResponse.json({ success: true, id });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

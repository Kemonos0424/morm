import { NextResponse } from 'next/server';
import { dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';
export async function POST(request) {
  const { nodeId } = await request.json();
  if (!nodeId) return NextResponse.json({ error: 'nodeId required' }, { status: 400 });

  const now = new Date().toISOString();
  await dbRun('UPDATE nodes SET status = ?, last_heartbeat = ? WHERE id = ?', ['online', now, nodeId]);

  return NextResponse.json({ status: 'ok', timestamp: now });
}

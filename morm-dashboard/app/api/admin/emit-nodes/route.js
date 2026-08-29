import { NextResponse } from 'next/server';
import { settleNodesProportional } from '@/app/lib/node-emission';

export const dynamic = 'force-dynamic';

// Phase 2-⑤ admin trigger: pay the NODE allocation of the epoch budget to nodes
// proportionally to their verified score. Guarded by ADMIN_PASSWORD (moves real
// MORM). Pass { password, epochLabel, dryRun }. Separate from /api/rewards so the
// legacy weekly-snapshot flow is untouched.
export async function POST(request) {
  try {
    const body = await request.json().catch(() => ({}));
    const adminPass = (process.env.ADMIN_PASSWORD || '').trim();  // fail-closed（既定 '1234' 撤廃）
    if (!adminPass || (body.password || '') !== adminPass) {
      return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
    }
    const epochLabel = (body.epochLabel || '').toString().trim();
    if (!epochLabel) {
      return NextResponse.json({ error: 'epochLabel required' }, { status: 400 });
    }
    const res = await settleNodesProportional({ epochLabel, dryRun: Boolean(body.dryRun) });
    const status = res.error ? 400 : 200;
    return NextResponse.json(res, { status });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

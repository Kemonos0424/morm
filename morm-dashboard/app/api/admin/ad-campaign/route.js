import { NextResponse } from 'next/server';
import { fundCampaign, settleCampaign, getCampaign } from '@/app/lib/ad-escrow';

export const dynamic = 'force-dynamic';

// Phase 2-⑥ admin control for ad campaigns. ADMIN_PASSWORD-gated (moves real
// MORM on settle). Actions:
//   { action:'fund',   campaignId, advertiser, units, depositTx }  record deposit
//   { action:'settle', campaignId, epochLabel, dryRun }            pay earners
//   { action:'status', campaignId }                                read budget
// Payouts are capped by the advertiser-funded budget — this is redistribution,
// never treasury emission (the /api/rewards + B_day emission are untouched).
export async function POST(request) {
  try {
    const body = await request.json().catch(() => ({}));
    const adminPass = (process.env.ADMIN_PASSWORD || '').trim();  // fail-closed（既定 '1234' 撤廃）
    if (!adminPass || (body.password || '') !== adminPass) {
      return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
    }
    const { action, campaignId } = body;
    if (!campaignId) return NextResponse.json({ error: 'campaignId required' }, { status: 400 });

    if (action === 'fund') {
      const res = await fundCampaign({
        campaignId, advertiser: body.advertiser,
        units: body.units, depositTx: body.depositTx,
      });
      return NextResponse.json({ ok: true, campaign: res });
    }
    if (action === 'settle') {
      const res = await settleCampaign({ campaignId, epochLabel: body.epochLabel, dryRun: Boolean(body.dryRun) });
      return NextResponse.json(res, { status: res.error ? 400 : 200 });
    }
    if (action === 'status') {
      const c = await getCampaign(campaignId);
      return NextResponse.json(c || { error: 'not found' }, { status: c ? 200 : 404 });
    }
    return NextResponse.json({ error: 'action must be fund|settle|status' }, { status: 400 });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

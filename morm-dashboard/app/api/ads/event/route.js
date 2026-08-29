import { NextResponse } from 'next/server';
import {
  isHexPubkey, isValidMormAddress, addressFromPubkey,
  verifyEd25519, adEventMessage,
} from '@/app/lib/morm-address';
import { getCampaign, recordAdEvent } from '@/app/lib/ad-escrow';

export const dynamic = 'force-dynamic';

// Phase 2-⑥ — record a verified ad event (impression|click). The serving node /
// creator SIGNS  MORM-AD-EVENT:v1:<campaignId>:<earner>:<kind>:<ref>  proving it
// served the ad; (campaign,kind,ref,earner) is UNIQUE so each ref pays once.
// Public + CORS * (auth is the signature). Accrual only — payout happens in the
// admin settle, capped by the campaign's advertiser-funded budget (no emission).
const KINDS = new Set(['impression', 'click']);
const REF_RE = /^[A-Za-z0-9:_-]{3,128}$/;
const cors = () => ({ 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' });

export async function OPTIONS() { return new Response(null, { status: 204, headers: cors() }); }

export async function POST(request) {
  const headers = cors();
  try {
    const { campaignId, earner, pubkey, kind, ref, sig } = await request.json().catch(() => ({}));
    if (!campaignId || typeof campaignId !== 'string') {
      return NextResponse.json({ error: 'campaignId required' }, { status: 400, headers });
    }
    if (!isValidMormAddress(earner)) {
      return NextResponse.json({ error: 'invalid earner m0r addr' }, { status: 400, headers });
    }
    if (!isHexPubkey(pubkey) || addressFromPubkey(Buffer.from(pubkey, 'hex')) !== earner) {
      return NextResponse.json({ error: 'pubkey does not match earner' }, { status: 400, headers });
    }
    if (!KINDS.has(kind)) {
      return NextResponse.json({ error: 'kind must be impression|click' }, { status: 400, headers });
    }
    if (!REF_RE.test(ref || '')) {
      return NextResponse.json({ error: 'ref must be 3-128 chars [A-Za-z0-9:_-]' }, { status: 400, headers });
    }
    if (typeof sig !== 'string' || !verifyEd25519(pubkey, adEventMessage(campaignId, earner, kind, ref), sig)) {
      return NextResponse.json({ error: 'invalid ad-event signature' }, { status: 401, headers });
    }
    const camp = await getCampaign(campaignId);
    if (!camp || camp.status !== 'active') {
      return NextResponse.json({ error: 'campaign not active' }, { status: 404, headers });
    }
    const r = await recordAdEvent({ campaignId, earner, kind, ref });
    if (!r.ok) return NextResponse.json({ error: 'already recorded for this ref', duplicate: true }, { status: 409, headers });
    return NextResponse.json({ ok: true, campaignId, earner, kind, weight: r.weight }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

import { NextResponse } from 'next/server';
import { isValidMormAddress } from '@/app/lib/morm-address';
import { getL1Account, mormL1ReadEnabled } from '@/app/lib/morm-l1';
import { unitsToMorm, baseUnitsPerMorm } from '@/app/lib/morm-units';
import { ensureLaneSchema, laneStats } from '@/app/lib/lane-schema';

export const dynamic = 'force-dynamic';

// Agent Lane — ME. An agent's on-chain state (balance/nonce/stake) plus its
// lane activity (published count, earn claims). Read-only, public, CORS *.
function cors() {
  return { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,OPTIONS', 'Vary': 'Origin' };
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: cors() });
}

export async function GET(request) {
  const headers = cors();
  try {
    const { searchParams } = new URL(request.url);
    const addr = searchParams.get('addr');
    if (!isValidMormAddress(addr)) {
      return NextResponse.json({ error: 'invalid m0r addr' }, { status: 400, headers });
    }
    await ensureLaneSchema();
    const l1 = await getL1Account(addr);
    const stats = await laneStats(addr);
    const balUnits = l1 ? Number(l1.balance || 0) : null;
    const stakeUnits = l1 ? Number(l1.stake || 0) : null;
    return NextResponse.json({
      addr,
      baseUnitsPerMorm: baseUnitsPerMorm(),
      chain: {
        wired: mormL1ReadEnabled(),
        // raw integer base units (unchanged for compatibility) …
        balance: balUnits,
        nonce: l1 ? Number(l1.nonce || 0) : null,
        stake: stakeUnits,
        // … plus MORM-denominated values via the single unit converter.
        balanceMorm: balUnits === null ? null : unitsToMorm(balUnits),
        stakeMorm: stakeUnits === null ? null : unitsToMorm(stakeUnits),
      },
      lane: stats,
    }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

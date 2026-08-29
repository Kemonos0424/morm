import { NextResponse } from 'next/server';
import { ensureLaneSchema, laneFeed } from '@/app/lib/lane-schema';

export const dynamic = 'force-dynamic';

// Agent Lane — FEED. Fetch-only JSON of recently published lane content. No auth
// (public read). CORS * so any agent harness can read it server-side or in-browser.
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
    const limit = Number(searchParams.get('limit') || 50);
    await ensureLaneSchema();
    const items = await laneFeed(limit);
    return NextResponse.json({ count: items.length, items }, { headers });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500, headers });
  }
}

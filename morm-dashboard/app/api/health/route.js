import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';

export async function POST() {
  return NextResponse.json({ status: 'ok', timestamp: new Date().toISOString() });
}

export async function GET() {
  return NextResponse.json({ status: 'ok', timestamp: new Date().toISOString() });
}

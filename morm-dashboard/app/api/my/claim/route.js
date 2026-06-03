import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
import path from 'path';
import fs from 'fs';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const address = searchParams.get('address');
  if (!address) return NextResponse.json({ claims: [] });

  // MORM L1 weekly reward snapshots (m0r). Directory is optional; absent → no claims.
  const merkleDir = path.join(process.cwd(), '..', 'morm-l1', 'reward-data');
  const claims = [];

  try {
    if (fs.existsSync(merkleDir)) {
      const files = fs.readdirSync(merkleDir).filter(f => f.endsWith('.json'));
      for (const file of files) {
        const data = JSON.parse(fs.readFileSync(path.join(merkleDir, file), 'utf-8'));
        const entry = (data.claims || []).find(
          c => c.address && c.address.toLowerCase() === address.toLowerCase()
        );
        if (entry) {
          claims.push({
            week: file.replace('.json', ''),
            amount: entry.amount,
            proofCount: (entry.proof || []).length,
            claimed: entry.claimed || false
          });
        }
      }
    }
  } catch (e) {
    console.error('merkle read error:', e);
  }

  return NextResponse.json({ claims });
}

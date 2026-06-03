import { NextResponse } from 'next/server';
import { dbAll, dbGet, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const rows = await dbAll('SELECT * FROM ad_settings ORDER BY id ASC');
    return NextResponse.json({ ads: rows });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { ad_type, ad_code, placement, enabled } = body;

    if (!ad_type) {
      return NextResponse.json({ error: 'ad_type is required' }, { status: 400 });
    }

    await dbRun(
      `INSERT INTO ad_settings (ad_type, ad_code, placement, enabled) VALUES (?, ?, ?, ?)`,
      [ad_type, ad_code || '', placement || 'all', enabled !== undefined ? enabled : 1]
    );

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function PUT(request) {
  try {
    const body = await request.json();
    const { id, ad_code, enabled } = body;

    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    const existing = await dbGet('SELECT * FROM ad_settings WHERE id = ?', [Number(id)]);
    if (!existing) {
      return NextResponse.json({ error: 'Ad setting not found' }, { status: 404 });
    }

    const newCode = ad_code !== undefined ? ad_code : existing.ad_code;
    const newEnabled = enabled !== undefined ? enabled : existing.enabled;

    await dbRun(
      `UPDATE ad_settings SET ad_code = ?, enabled = ? WHERE id = ?`,
      [newCode, newEnabled, Number(id)]
    );

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function DELETE(request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }

    await dbRun('DELETE FROM ad_settings WHERE id = ?', [Number(id)]);
    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

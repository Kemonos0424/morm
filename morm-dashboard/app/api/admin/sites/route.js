import { NextResponse } from 'next/server';
import { dbAll, dbRun, dbGet } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const sites = await dbAll('SELECT * FROM sites ORDER BY created_at DESC');
    return NextResponse.json({ sites });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { title, slug, site_type, design_template, design_source, theme, keywords } = body;

    if (!title) {
      return NextResponse.json({ error: 'title is required' }, { status: 400 });
    }

    const finalSlug = slug || title.toLowerCase().replace(/[^a-z0-9\u3000-\u9fff]+/g, '-').replace(/^-|-$/g, '');

    const result = await dbRun(
      `INSERT INTO sites (title, slug, site_type, design_template, design_source, theme, keywords)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [title, finalSlug, site_type || 'blog', design_template || null, design_source || 'jp', theme || null, keywords || null]
    );

    const site = await dbGet('SELECT * FROM sites WHERE id = ?', [Number(result.lastInsertRowid)]);
    return NextResponse.json({ site });
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
    await dbRun('DELETE FROM site_pages WHERE site_id = ?', [Number(id)]);
    await dbRun('DELETE FROM sites WHERE id = ?', [Number(id)]);
    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

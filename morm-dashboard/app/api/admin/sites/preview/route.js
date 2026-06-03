import { NextResponse } from 'next/server';
import { dbGet } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return new Response('<h1>ID required</h1>', {
        status: 400,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      });
    }

    const site = await dbGet('SELECT html_content, title FROM sites WHERE id = ?', [Number(id)]);
    if (!site || !site.html_content) {
      return new Response('<h1>Site not found or not generated yet</h1>', {
        status: 404,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      });
    }

    return new Response(site.html_content, {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

import { NextResponse } from 'next/server';
import { dbAll, dbGet, dbRun } from '@/app/lib/db';
import { generateBlogSite, generateLPSite, injectAds } from '@/app/lib/site-generator';

export const dynamic = 'force-dynamic';

export async function POST(request) {
  try {
    const body = await request.json();
    const { site_id } = body;

    if (!site_id) {
      return NextResponse.json({ error: 'site_id is required' }, { status: 400 });
    }

    const site = await dbGet('SELECT * FROM sites WHERE id = ?', [Number(site_id)]);
    if (!site) {
      return NextResponse.json({ error: 'Site not found' }, { status: 404 });
    }

    const config = {
      title: site.title,
      theme: site.theme || 'テクノロジー',
      keywords: site.keywords || '',
      designTemplate: site.design_template || 'apple',
      designSource: site.design_source || 'jp',
    };

    let result;
    if (site.site_type === 'lp') {
      result = generateLPSite(config);
    } else {
      result = generateBlogSite(config);
    }

    // Inject ads from ad_settings
    const adSettings = await dbAll('SELECT * FROM ad_settings WHERE enabled = 1');
    result.html = injectAds(result.html, adSettings);

    // Save HTML to sites table
    await dbRun(
      `UPDATE sites SET html_content = ?, status = 'generated', updated_at = datetime('now') WHERE id = ?`,
      [result.html, Number(site_id)]
    );

    // Delete old pages for this site
    await dbRun('DELETE FROM site_pages WHERE site_id = ?', [Number(site_id)]);

    // Insert new pages
    for (let i = 0; i < result.pages.length; i++) {
      const page = result.pages[i];
      await dbRun(
        `INSERT INTO site_pages (site_id, title, slug, content, page_type, sort_order) VALUES (?, ?, ?, ?, 'article', ?)`,
        [Number(site_id), page.title, page.slug, page.content, i]
      );
    }

    return NextResponse.json({
      success: true,
      html_preview_length: result.html.length,
      pages_count: result.pages.length,
    });
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

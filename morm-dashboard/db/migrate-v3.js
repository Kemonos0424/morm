import { createClient } from '@libsql/client';
import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
config({ path: resolve(__dirname, '..', '.env.local') });

const url = (process.env.TURSO_DATABASE_URL || '').trim();
const authToken = (process.env.TURSO_AUTH_TOKEN || '').trim();

let client;
if (url && authToken) {
  client = createClient({ url, authToken });
} else {
  client = createClient({ url: 'file:db/dashboard.sqlite' });
}

async function run(sql, label) {
  try {
    await client.execute(sql);
    console.log(`[OK] ${label}`);
  } catch (e) {
    if (e.message && (e.message.includes('duplicate column') || e.message.includes('already exists'))) {
      console.log(`[SKIP] ${label} (already exists)`);
    } else {
      console.error(`[ERR] ${label}:`, e.message);
    }
  }
}

async function migrate() {
  console.log('=== migrate-v3 start ===');

  await run(`CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    slug TEXT,
    site_type TEXT DEFAULT 'blog',
    design_template TEXT,
    design_source TEXT DEFAULT 'jp',
    theme TEXT,
    keywords TEXT,
    status TEXT DEFAULT 'draft',
    html_content TEXT,
    meta_description TEXT,
    og_image TEXT,
    node_id TEXT,
    published_url TEXT,
    ad_code TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
  )`, 'CREATE sites');

  await run(`CREATE TABLE IF NOT EXISTS site_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER,
    title TEXT,
    slug TEXT,
    content TEXT,
    page_type TEXT DEFAULT 'article',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
  )`, 'CREATE site_pages');

  console.log('=== migrate-v3 done ===');
  process.exit(0);
}

migrate().catch(e => { console.error(e); process.exit(1); });

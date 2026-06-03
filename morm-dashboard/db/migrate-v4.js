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
  console.log('=== migrate-v4 start ===');

  await run(`CREATE TABLE IF NOT EXISTS ad_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_type TEXT NOT NULL,
    ad_code TEXT,
    placement TEXT DEFAULT 'all',
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
  )`, 'CREATE ad_settings');

  console.log('=== migrate-v4 done ===');
  process.exit(0);
}

migrate().catch(e => { console.error(e); process.exit(1); });

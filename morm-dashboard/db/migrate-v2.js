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
  console.log('=== migrate-v2 start ===');

  // New tables
  await run(`CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT,
    service TEXT,
    credential_type TEXT,
    label TEXT,
    data TEXT,
    verified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
  )`, 'CREATE credentials');

  await run(`CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT,
    sender TEXT,
    message TEXT,
    read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
  )`, 'CREATE messages');

  // ALTER tasks
  await run(`ALTER TABLE tasks ADD COLUMN morm_cost REAL DEFAULT 0`, 'tasks.morm_cost');
  await run(`ALTER TABLE tasks ADD COLUMN requires_credential TEXT`, 'tasks.requires_credential');
  await run(`ALTER TABLE tasks ADD COLUMN auto_trigger TEXT`, 'tasks.auto_trigger');
  await run(`ALTER TABLE tasks ADD COLUMN cooldown_hours INTEGER DEFAULT 0`, 'tasks.cooldown_hours');

  // ALTER nodes
  await run(`ALTER TABLE nodes ADD COLUMN morm_balance REAL DEFAULT 0`, 'nodes.morm_balance');
  await run(`ALTER TABLE nodes ADD COLUMN morm_pending REAL DEFAULT 0`, 'nodes.morm_pending');
  await run(`ALTER TABLE nodes ADD COLUMN morm_spent REAL DEFAULT 0`, 'nodes.morm_spent');

  // UPDATE tasks with morm_cost, requires_credential, auto_trigger
  const taskUpdates = [
    { id: 'auto_rule', morm_cost: 5, requires_credential: null, auto_trigger: null },
    { id: 'article_gen', morm_cost: 2, requires_credential: null, auto_trigger: null },
    { id: 'api_connect', morm_cost: 10, requires_credential: 'custom', auto_trigger: null },
    { id: 'sns_connect_x', morm_cost: 0, requires_credential: 'x', auto_trigger: null },
    { id: 'sns_connect_ig', morm_cost: 0, requires_credential: 'instagram', auto_trigger: null },
    { id: 'sns_connect_tt', morm_cost: 0, requires_credential: 'tiktok', auto_trigger: null },
    { id: 'sns_connect_fb', morm_cost: 0, requires_credential: 'facebook', auto_trigger: null },
    { id: 'sns_connect_yt', morm_cost: 0, requires_credential: 'youtube', auto_trigger: null },
    { id: 'sns_post', morm_cost: 0, requires_credential: 'x', auto_trigger: null },
    { id: 'gmail_connect', morm_cost: 0, requires_credential: 'gmail', auto_trigger: null },
    { id: 'git_setup', morm_cost: 0, requires_credential: 'git', auto_trigger: 'on_connect' },
    { id: 'cf_tunnel', morm_cost: 0, requires_credential: 'cloudflare', auto_trigger: 'on_connect' },
    { id: 'site_publish', morm_cost: 0, requires_credential: null, auto_trigger: 'on_connect' },
    { id: 'vpn_join', morm_cost: 0, requires_credential: null, auto_trigger: 'on_connect' },
    { id: 'storage_share', morm_cost: 0, requires_credential: null, auto_trigger: 'on_connect' },
    { id: 'review_submit', morm_cost: 0, requires_credential: null, auto_trigger: 'on_schedule' },
  ];

  for (const t of taskUpdates) {
    await run(
      `UPDATE tasks SET morm_cost = ${t.morm_cost}, requires_credential = ${t.requires_credential ? `'${t.requires_credential}'` : 'NULL'}, auto_trigger = ${t.auto_trigger ? `'${t.auto_trigger}'` : 'NULL'} WHERE id = '${t.id}'`,
      `UPDATE task ${t.id}`
    );
  }

  // UPDATE nodes: set morm_pending and morm_balance from task_score
  await run(
    `UPDATE nodes SET morm_pending = task_score / 100.0, morm_balance = task_score / 100.0`,
    'UPDATE nodes morm from task_score'
  );

  console.log('=== migrate-v2 done ===');
  process.exit(0);
}

migrate().catch(e => { console.error(e); process.exit(1); });

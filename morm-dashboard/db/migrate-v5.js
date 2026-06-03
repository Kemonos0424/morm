import { createClient } from '@libsql/client';
import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { randomBytes } from 'crypto';

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

async function run(sql, label, args = []) {
  try {
    await client.execute({ sql, args });
    console.log(`[OK] ${label}`);
  } catch (e) {
    if (e.message && (e.message.includes('duplicate column') || e.message.includes('already exists'))) {
      console.log(`[SKIP] ${label} (already exists)`);
    } else {
      console.error(`[ERR] ${label}:`, e.message);
    }
  }
}

// Map known executable tasks to real shell commands run on the node.
// Tasks without a command keep the instant local behavior (connection toggles etc.).
const TASK_COMMANDS = {
  site_publish: 'sudo systemctl reload nginx',
  git_setup: 'git --version',
  cf_tunnel: 'cloudflared --version',
  storage_share: 'df -h / | tail -1',
  vpn_join: 'tailscale status | head -1',
  review_submit: 'echo review-ok',
};

async function migrate() {
  console.log('=== migrate-v5 start ===');

  await run(`ALTER TABLE tasks ADD COLUMN command TEXT`, 'tasks.command');
  await run(`ALTER TABLE tasks ADD COLUMN timeout_sec INTEGER DEFAULT 300`, 'tasks.timeout_sec');

  await run(`ALTER TABLE task_runs ADD COLUMN created_at TEXT`, 'task_runs.created_at');
  await run(`ALTER TABLE task_runs ADD COLUMN started_at TEXT`, 'task_runs.started_at');

  await run(`ALTER TABLE nodes ADD COLUMN agent_token TEXT`, 'nodes.agent_token');

  // Seed commands for known tasks
  for (const [id, cmd] of Object.entries(TASK_COMMANDS)) {
    await run(`UPDATE tasks SET command = ? WHERE id = ? AND (command IS NULL OR command = '')`, `seed command ${id}`, [cmd, id]);
  }

  // Generate agent_token for existing nodes that lack one
  const { rows } = await client.execute(`SELECT id FROM nodes WHERE agent_token IS NULL OR agent_token = ''`);
  for (const r of rows) {
    const token = randomBytes(24).toString('hex');
    await run(`UPDATE nodes SET agent_token = ? WHERE id = ?`, `agent_token ${r.id}`, [token, r.id]);
  }

  console.log('=== migrate-v5 done ===');
  process.exit(0);
}

migrate().catch(e => { console.error(e); process.exit(1); });

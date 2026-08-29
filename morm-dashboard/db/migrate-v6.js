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
  console.log('=== migrate-v6 start (walletless MORM accounts) ===');

  // End-user MORM wallets created from the public site. Walletless / non-custodial:
  // the private ed25519 seed NEVER touches the server — only the public address,
  // pubkey, and (optionally) the WebAuthn credential id are stored here.
  await run(`CREATE TABLE IF NOT EXISTS morm_accounts (
    address         TEXT PRIMARY KEY,
    handle          TEXT UNIQUE,
    pubkey          TEXT NOT NULL,
    passkey_cred_id TEXT,
    faucet_tx       TEXT,
    faucet_status   TEXT DEFAULT 'pending',
    ip_hash         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
  )`, 'morm_accounts table');

  await run(`CREATE INDEX IF NOT EXISTS idx_morm_accounts_handle ON morm_accounts(handle)`, 'idx handle');
  await run(`CREATE INDEX IF NOT EXISTS idx_morm_accounts_created ON morm_accounts(created_at)`, 'idx created');

  console.log('=== migrate-v6 done ===');
  process.exit(0);
}

migrate().catch((e) => { console.error(e); process.exit(1); });

import { createClient } from '@libsql/client';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

const __dirname = dirname(fileURLToPath(import.meta.url));

const client = createClient({
  url: process.env.TURSO_DATABASE_URL,
  authToken: process.env.TURSO_AUTH_TOKEN
});

async function main() {
  console.log('Dropping existing tables...');
  const tables = ['weekly_snapshots', 'task_runs', 'connections', 'wallets', 'tasks', 'nodes'];
  for (const t of tables) {
    await client.execute(`DROP TABLE IF EXISTS ${t}`);
    console.log(`  Dropped ${t}`);
  }

  console.log('Creating tables from schema.sql...');
  const schema = readFileSync(join(__dirname, 'schema.sql'), 'utf8');
  const statements = schema.split(';').map(s => s.trim()).filter(s => s.length > 0);
  for (const stmt of statements) {
    await client.execute(stmt);
  }
  console.log('Schema applied.');

  console.log('Done! Run seed-turso.js next.');
}

main().catch(e => { console.error(e); process.exit(1); });

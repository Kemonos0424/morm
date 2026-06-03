import { createClient } from '@libsql/client';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const url = process.env.TURSO_DATABASE_URL;
const authToken = process.env.TURSO_AUTH_TOKEN;

if (!url || !authToken) {
  console.error('TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set');
  process.exit(1);
}

const client = createClient({ url, authToken });

async function main() {
  const schema = readFileSync(join(__dirname, 'schema.sql'), 'utf-8');
  const statements = schema
    .split(';')
    .map(s => s.trim())
    .filter(s => s.length > 0);

  for (const stmt of statements) {
    try {
      await client.execute(stmt);
      console.log('OK:', stmt.slice(0, 60) + '...');
    } catch (e) {
      console.error('ERR:', stmt.slice(0, 60), e.message);
    }
  }

  console.log('Turso DB initialized successfully');
}

main().catch(e => { console.error(e); process.exit(1); });

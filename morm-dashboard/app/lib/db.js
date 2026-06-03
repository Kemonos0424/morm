import { createClient } from '@libsql/client';

let client;

export function getDb() {
  if (!client) {
    const url = (process.env.TURSO_DATABASE_URL || '').trim();
    const authToken = (process.env.TURSO_AUTH_TOKEN || '').trim();

    if (url && authToken) {
      // Turso (production / Vercel)
      client = createClient({ url, authToken });
    } else {
      // Local fallback: file-based SQLite
      client = createClient({ url: 'file:db/dashboard.sqlite' });
    }
  }
  return client;
}

// Helper: run query and return rows (Turso returns { rows: [...] })
export async function dbAll(sql, params = []) {
  const db = getDb();
  const result = await db.execute({ sql, args: params });
  return result.rows;
}

export async function dbGet(sql, params = []) {
  const rows = await dbAll(sql, params);
  return rows[0] || null;
}

export async function dbRun(sql, params = []) {
  const db = getDb();
  return await db.execute({ sql, args: params });
}

export async function dbExec(sql) {
  const db = getDb();
  // Split multiple statements
  const statements = sql.split(';').map(s => s.trim()).filter(s => s.length > 0);
  for (const stmt of statements) {
    await db.execute(stmt);
  }
}

import { createClient } from '@libsql/client';
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

const url = process.env.TURSO_DATABASE_URL;
const authToken = process.env.TURSO_AUTH_TOKEN;

if (!url || !authToken) {
  console.error('TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set');
  process.exit(1);
}

const client = createClient({ url, authToken });

async function main() {
  // Clear existing data
  console.log('Clearing existing data...');
  await client.execute('DELETE FROM task_runs');
  await client.execute('DELETE FROM connections');
  await client.execute('DELETE FROM wallets');
  await client.execute('DELETE FROM weekly_snapshots');
  await client.execute('DELETE FROM nodes');

  // Seed real nodes
  console.log('Seeding nodes...');

  // Claude PC1
  const pc1Score = Math.round(4 * 10 + 8.3 * 5 + 1007 * 0.1);
  await client.execute({
    sql: `INSERT INTO nodes (id, name, ssh_host, ssh_port, ssh_user, ssh_pass, status, cpu_cores, ram_gb, storage_gb, storage_used_gb, base_score, task_score, total_score, tailscale_ip, wireguard_ip, wallet_address, connection_methods, last_heartbeat)
          VALUES (?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, ?, ?, 155, ?, ?, ?, ?, 'Local,SSH', datetime('now'))`,
    args: ['claude_pc1', 'Claude PC1', '221.241.79.54', 22222, 'claude_pc1', 'redm/2026',
           4, 8.3, 1007, 7, pc1Score, pc1Score + 155,
           '100.95.248.72', '10.0.0.1', '0xAAB6490FAf8C2CD0a5392251c44f43dB6aC3AB37']
  });
  console.log(`  Claude PC1: score ${pc1Score + 155}`);

  // Mac Mini
  const mmScore = Math.round(8 * 10 + 16 * 5 + 500 * 0.1);
  await client.execute({
    sql: `INSERT INTO nodes (id, name, ssh_host, ssh_port, ssh_user, ssh_pass, status, cpu_cores, ram_gb, storage_gb, storage_used_gb, base_score, task_score, total_score, tailscale_ip, wallet_address, connection_methods, last_heartbeat)
          VALUES (?, ?, ?, ?, ?, ?, 'online', ?, ?, ?, ?, ?, 0, ?, ?, ?, 'Tailscale', datetime('now'))`,
    args: ['mac_mini', 'Mac Mini (Apple Silicon)', '192.168.2.122', 22, 'user', '9999',
           8, 16, 500, 100, mmScore, mmScore,
           '100.108.60.73', '0x852D3699D0c159Da48FB4632Ce792CDbfd4801Db']
  });
  console.log(`  Mac Mini: score ${mmScore}`);

  // Wallets
  console.log('Seeding wallets...');
  await client.execute({
    sql: 'INSERT INTO wallets (node_id, address) VALUES (?, ?)',
    args: ['claude_pc1', '0xAAB6490FAf8C2CD0a5392251c44f43dB6aC3AB37']
  });
  await client.execute({
    sql: 'INSERT INTO wallets (node_id, address) VALUES (?, ?)',
    args: ['mac_mini', '0x852D3699D0c159Da48FB4632Ce792CDbfd4801Db']
  });

  // Connections
  console.log('Seeding connections...');
  const services = ['x', 'instagram', 'tiktok', 'facebook', 'youtube', 'gmail', 'git', 'cloudflare'];
  for (const s of services) {
    const connected = (s === 'git' || s === 'cloudflare');
    await client.execute({
      sql: `INSERT INTO connections (node_id, service, status, account_name) VALUES (?, ?, ?, ?)`,
      args: ['claude_pc1', s, connected ? 'connected' : 'disconnected', connected ? (s === 'git' ? 'Kemonos0424' : 'trycloudflare') : null]
    });
  }
  for (const s of services) {
    await client.execute({
      sql: `INSERT INTO connections (node_id, service, status) VALUES (?, ?, 'disconnected')`,
      args: ['mac_mini', s]
    });
  }

  // Task runs for claude_pc1
  console.log('Seeding task runs...');
  const taskRuns = [
    ['claude_pc1', 'vpn_join', 'success', 30],
    ['claude_pc1', 'cf_tunnel', 'success', 20],
    ['claude_pc1', 'git_setup', 'success', 10],
    ['claude_pc1', 'site_publish', 'success', 10],
    ['claude_pc1', 'site_publish', 'success', 10],
    ['claude_pc1', 'auto_rule', 'success', 15],
    ['claude_pc1', 'site_publish', 'success', 10],
    ['claude_pc1', 'storage_share', 'success', 25],
    ['claude_pc1', 'article_gen', 'success', 10],
    ['claude_pc1', 'review_submit', 'success', 5],
    ['claude_pc1', 'sns_post', 'success', 5],
    ['claude_pc1', 'gmail_connect', 'success', 5],
  ];
  for (const [nodeId, taskId, status, score] of taskRuns) {
    await client.execute({
      sql: `INSERT INTO task_runs (node_id, task_id, status, score_earned, completed_at) VALUES (?, ?, ?, ?, datetime('now'))`,
      args: [nodeId, taskId, status, score]
    });
  }

  console.log('Turso DB seeded successfully!');
}

main().catch(e => { console.error(e); process.exit(1); });

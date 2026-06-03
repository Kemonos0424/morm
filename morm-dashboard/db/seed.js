const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = path.join(__dirname, 'dashboard.sqlite');
const SCHEMA_PATH = path.join(__dirname, 'schema.sql');

// Remove existing DB for clean seed
if (fs.existsSync(DB_PATH)) fs.unlinkSync(DB_PATH);

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Run schema
const schema = fs.readFileSync(SCHEMA_PATH, 'utf-8');
db.exec(schema);

console.log('Schema created.');

// Seed nodes
const insertNode = db.prepare(`
  INSERT INTO nodes (name, ssh_host, ssh_port, ssh_user, cpu_cores, ram_gb, storage_gb, storage_used_gb,
    base_score, task_score, total_score, tailscale_ip, wireguard_ip, wallet_address, connection_methods, status, last_heartbeat)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
`);

// claude_pc1: 4c * 10 + 8.3 * 5 + 1007 * 0.1 = 40 + 41.5 + 100.7 = 182.2 base
// task_score to reach 337 total: 337 - 182.2 = 154.8
const pc1Id = insertNode.run(
  'claude_pc1', '221.241.79.54', 22222, 'claude_pc1',
  4, 8.3, 1007, 250,
  182.2, 154.8, 337,
  '100.95.248.72', '10.0.0.1',
  '0xAAB6490FAf8C2CD0a5392251c44f43dB6aC3AB37',
  '["SSH","Tailscale","WireGuard"]', 'online'
).lastInsertRowid;

// Mac Mini: 8c * 10 + 16 * 5 + 500 * 0.1 = 80 + 80 + 50 = 210 base
const miniId = insertNode.run(
  'Mac Mini', '192.168.2.122', 22, 'user',
  8, 16, 500, 120,
  210, 0, 210,
  '100.108.60.73', null,
  '0x852D3699D0c159Da48FB4632Ce792CDbfd4801Db',
  '["SSH","Tailscale","LAN"]', 'online'
).lastInsertRowid;

console.log(`Nodes created: claude_pc1 (${pc1Id}), Mac Mini (${miniId})`);

// Seed connections
const insertConn = db.prepare(`
  INSERT INTO connections (node_id, service, method, endpoint, status) VALUES (?, ?, ?, ?, 'active')
`);

// claude_pc1 connections
insertConn.run(pc1Id, 'nginx', 'SSH', '221.241.79.54:22222');
insertConn.run(pc1Id, 'cloudflared', 'Tailscale', '100.95.248.72');
insertConn.run(pc1Id, 'tailscale', 'Tailscale', '100.95.248.72');
insertConn.run(pc1Id, 'wireguard', 'WireGuard', '10.0.0.1');
insertConn.run(pc1Id, 'gitea', 'SSH', '221.241.79.54:22222');
insertConn.run(pc1Id, 'cron', 'Local', 'localhost');
insertConn.run(pc1Id, 'backup', 'SSH', '221.241.79.54:22222');
insertConn.run(pc1Id, 'api', 'Tailscale', '100.95.248.72:3000');

// Mac Mini connections
insertConn.run(miniId, 'nginx', 'LAN', '192.168.2.122');
insertConn.run(miniId, 'cloudflared', 'Tailscale', '100.108.60.73');
insertConn.run(miniId, 'tailscale', 'Tailscale', '100.108.60.73');
insertConn.run(miniId, 'cron', 'Local', 'localhost');
insertConn.run(miniId, 'backup', 'LAN', '192.168.2.122');

console.log('Connections created.');

// Seed task_runs
const insertRun = db.prepare(`
  INSERT INTO task_runs (node_id, task_id, status, score_earned, executed_at) VALUES (?, ?, ?, ?, ?)
`);

// claude_pc1 task runs
insertRun.run(pc1Id, 1, 'success', 15, '2025-04-01 10:00:00');   // Web hosting
insertRun.run(pc1Id, 2, 'success', 10, '2025-04-01 10:05:00');   // SSL
insertRun.run(pc1Id, 7, 'success', 12, '2025-04-01 10:10:00');   // Git server
insertRun.run(pc1Id, 8, 'success', 15, '2025-04-01 10:15:00');   // CI/CD
insertRun.run(pc1Id, 9, 'success', 12, '2025-04-02 08:00:00');   // cloudflare tunnel
insertRun.run(pc1Id, 11, 'success', 10, '2025-04-02 08:05:00');  // cron
insertRun.run(pc1Id, 12, 'success', 12, '2025-04-02 08:10:00');  // backup
insertRun.run(pc1Id, 13, 'success', 15, '2025-04-02 08:15:00');  // API server
insertRun.run(pc1Id, 14, 'success', 12, '2025-04-03 09:00:00');  // P2P
insertRun.run(pc1Id, 15, 'success', 10, '2025-04-03 09:05:00');  // storage
insertRun.run(pc1Id, 3, 'success', 10, '2025-04-03 09:10:00');   // SNS auto post
insertRun.run(pc1Id, 5, 'success', 10, '2025-04-04 12:00:00');   // email forward
insertRun.run(pc1Id, 16, 'failed', 0, '2025-04-04 12:05:00');    // code review failed
insertRun.run(pc1Id, 4, 'success', 8, '2025-04-05 14:00:00');    // SNS engagement
insertRun.run(pc1Id, 10, 'success', 8, '2025-04-05 14:05:00');   // DNS

// Mac Mini task runs
insertRun.run(miniId, 1, 'success', 15, '2025-04-01 11:00:00');
insertRun.run(miniId, 9, 'success', 12, '2025-04-01 11:05:00');
insertRun.run(miniId, 11, 'success', 10, '2025-04-02 09:00:00');
insertRun.run(miniId, 12, 'success', 12, '2025-04-02 09:05:00');

console.log('Task runs created.');

// Seed wallets
db.prepare('INSERT OR IGNORE INTO wallets (address) VALUES (?)').run('0xaab6490faf8c2cd0a5392251c44f43db6ac3ab37');
db.prepare('INSERT OR IGNORE INTO wallets (address) VALUES (?)').run('0x852d3699d0c159da48fb4632ce792cdbfd4801db');

console.log('Wallets created.');
console.log('Seed completed successfully!');

db.close();

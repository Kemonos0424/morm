CREATE TABLE IF NOT EXISTS nodes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  ssh_host TEXT,
  ssh_port INTEGER DEFAULT 22,
  ssh_user TEXT,
  ssh_pass TEXT,
  status TEXT DEFAULT 'offline',
  cpu_cores INTEGER DEFAULT 0,
  ram_gb REAL DEFAULT 0,
  storage_gb REAL DEFAULT 0,
  storage_used_gb REAL DEFAULT 0,
  base_score INTEGER DEFAULT 0,
  task_score INTEGER DEFAULT 0,
  total_score INTEGER DEFAULT 0,
  tailscale_ip TEXT,
  wireguard_ip TEXT,
  wallet_address TEXT,
  connection_methods TEXT DEFAULT '',
  gas_stipend_sent INTEGER DEFAULT 0,
  gas_stipend_tx TEXT,
  morm_balance REAL DEFAULT 0,
  morm_pending REAL DEFAULT 0,
  morm_spent REAL DEFAULT 0,
  agent_token TEXT,
  last_heartbeat TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  score_value INTEGER DEFAULT 0,
  auto INTEGER DEFAULT 0,
  morm_cost REAL DEFAULT 0,
  requires_credential TEXT,
  auto_trigger TEXT,
  cooldown_hours INTEGER DEFAULT 0,
  command TEXT,
  timeout_sec INTEGER DEFAULT 300
);

CREATE TABLE IF NOT EXISTS task_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT REFERENCES nodes(id),
  task_id TEXT REFERENCES tasks(id),
  status TEXT DEFAULT 'pending',
  result TEXT,
  score_earned INTEGER DEFAULT 0,
  created_at TEXT,
  started_at TEXT,
  completed_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS connections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT REFERENCES nodes(id),
  service TEXT NOT NULL,
  status TEXT DEFAULT 'disconnected',
  account_name TEXT,
  connected_at TEXT
);

CREATE TABLE IF NOT EXISTS wallets (
  node_id TEXT PRIMARY KEY REFERENCES nodes(id),
  address TEXT NOT NULL,
  connected_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS weekly_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT REFERENCES nodes(id),
  week_label TEXT,
  wallet_address TEXT,
  total_score INTEGER DEFAULT 0,
  morm_amount REAL DEFAULT 0,
  tx_hash TEXT,
  status TEXT DEFAULT 'pending',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credentials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT,
  service TEXT,
  credential_type TEXT,
  label TEXT,
  data TEXT,
  verified INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id TEXT,
  sender TEXT,
  message TEXT,
  read INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

-- Ad settings (v4)
CREATE TABLE IF NOT EXISTS ad_settings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ad_type TEXT NOT NULL,
  ad_code TEXT,
  placement TEXT DEFAULT 'all',
  enabled INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);

-- Default tasks (explicit columns; command seeded for node-executable tasks)
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('site_publish', 'site', 'サイト公開', 'nginxでサイトを公開', 10, 1, 0, NULL, 'on_connect', 0, 'sudo systemctl reload nginx', 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('sns_connect_x', 'sns', 'X接続', 'Xアカウント連携', 20, 0, 0, 'x', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('sns_connect_ig', 'sns', 'Instagram接続', 'IGアカウント連携', 20, 0, 0, 'instagram', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('sns_connect_tt', 'sns', 'TikTok接続', 'TikTokアカウント連携', 20, 0, 0, 'tiktok', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('sns_connect_fb', 'sns', 'Facebook接続', 'FBアカウント連携', 20, 0, 0, 'facebook', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('sns_connect_yt', 'sns', 'YouTube接続', 'YTアカウント連携', 20, 0, 0, 'youtube', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('sns_post', 'sns', 'SNS自動投稿', 'スケジュール投稿実行', 5, 1, 0, 'x', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('gmail_connect', 'gmail', 'Gmail連携', 'Gmail設定', 15, 0, 0, 'gmail', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('git_setup', 'git', 'Git設定', 'リポジトリ設定', 10, 1, 0, 'git', 'on_connect', 0, 'git --version', 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('cf_tunnel', 'cloudflare', 'CFトンネル設定', 'Cloudflareトンネル', 20, 1, 0, 'cloudflare', 'on_connect', 0, 'cloudflared --version', 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('auto_rule', 'automation', '自動化ルール', '自動化設定', 15, 1, 5, NULL, NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('article_gen', 'automation', '記事生成', '記事自動生成', 10, 1, 2, NULL, NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('api_connect', 'api', 'API連携', '外部API接続', 20, 0, 10, 'custom', NULL, 0, NULL, 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('vpn_join', 'p2p', 'VPN参加', 'P2P VPN接続', 30, 1, 0, NULL, 'on_connect', 0, 'tailscale status | head -1', 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('storage_share', 'storage', 'ストレージ共有', 'NFS/rsync共有', 25, 1, 0, NULL, 'on_connect', 0, 'df -h / | tail -1', 300);
INSERT OR IGNORE INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec) VALUES ('review_submit', 'review', 'レビュー', '自動レビュー', 5, 1, 0, NULL, 'on_schedule', 0, 'echo review-ok', 300);

-- Sites (v3)
CREATE TABLE IF NOT EXISTS sites (
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
);

CREATE TABLE IF NOT EXISTS site_pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id INTEGER,
  title TEXT,
  slug TEXT,
  content TEXT,
  page_type TEXT DEFAULT 'article',
  sort_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

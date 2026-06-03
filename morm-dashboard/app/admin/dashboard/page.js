import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export default async function AdminDashboard() {
  const nodes = await dbAll('SELECT * FROM nodes ORDER BY total_score DESC');
  const onlineCount = nodes.filter(n => n.status === 'online').length;
  const totalScore = Math.round(nodes.reduce((s, n) => s + (n.total_score || 0), 0));
  const walletCount = nodes.filter(n => n.wallet_address).length;
  const recentRuns = await dbAll(`
    SELECT tr.*, t.name as task_name, n.name as node_name
    FROM task_runs tr
    JOIN tasks t ON tr.task_id = t.id
    JOIN nodes n ON tr.node_id = n.id
    ORDER BY tr.completed_at DESC LIMIT 10
  `);

  return (
    <div>
      <h1>管理ダッシュボード</h1>
      <div className="grid-4 mb-2">
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--green)' }}>{onlineCount}</div>
          <div className="stat-label">オンライン数</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{nodes.length}</div>
          <div className="stat-label">総ノード数</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalScore}</div>
          <div className="stat-label">合計スコア</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: 'var(--yellow)' }}>{walletCount}</div>
          <div className="stat-label">ウォレット接続済</div>
        </div>
      </div>

      <h2>トップノード</h2>
      <div className="card mb-2">
        <table>
          <thead>
            <tr><th>#</th><th>ノード</th><th>ステータス</th><th>CPU</th><th>RAM</th><th>Storage</th><th>スコア</th><th>ウォレット</th></tr>
          </thead>
          <tbody>
            {nodes.slice(0, 10).map((n, i) => (
              <tr key={n.id}>
                <td style={{display:'flex',alignItems:'center',gap:4}}>{i === 0 && <img src="/icons/score-trophy.svg" width={18} height={18} alt="" />}{i + 1}</td>
                <td>{n.name}</td>
                <td><img src={n.status === 'online' ? '/icons/status-online.svg' : '/icons/status-offline.svg'} width={18} height={18} alt={n.status} title={n.status} /></td>
                <td>{n.cpu_cores}c</td>
                <td>{n.ram_gb}GB</td>
                <td>{n.storage_gb}GB</td>
                <td><strong>{n.total_score}</strong></td>
                <td className="text-sm" style={{ fontFamily: 'monospace' }}>{n.wallet_address ? `${n.wallet_address.slice(0, 6)}...${n.wallet_address.slice(-4)}` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>最近のアクティビティ</h2>
      <div className="card">
        <table>
          <thead>
            <tr><th>タスク</th><th>ノード</th><th>ステータス</th><th>スコア</th><th>実行日</th></tr>
          </thead>
          <tbody>
            {recentRuns.map(r => (
              <tr key={r.id}>
                <td>{r.task_name}</td>
                <td>{r.node_name}</td>
                <td><span className={`badge ${r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'yellow'}`}>{r.status}</span></td>
                <td>{r.score_earned}</td>
                <td className="text-muted text-sm">{r.completed_at}</td>
              </tr>
            ))}
            {recentRuns.length === 0 && <tr><td colSpan={5} className="text-muted text-center">アクティビティなし</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

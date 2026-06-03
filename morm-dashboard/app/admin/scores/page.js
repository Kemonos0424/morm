import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export default async function ScoresPage() {
  const nodes = await dbAll('SELECT * FROM nodes ORDER BY total_score DESC');

  return (
    <div>
      <h1>スコアボード</h1>
      <div className="card">
        <table>
          <thead>
            <tr><th>ランク</th><th>ノード</th><th>CPU</th><th>RAM</th><th>Storage</th><th>ベース</th><th>タスク</th><th>合計</th><th>MORM換算</th><th>ウォレット</th></tr>
          </thead>
          <tbody>
            {nodes.map((n, i) => (
              <tr key={n.id}>
                <td style={{ fontWeight: 700, color: i < 3 ? 'var(--yellow)' : 'var(--text)', display:'flex', alignItems:'center', gap:4 }}>{i === 0 && <img src="/icons/score-trophy.svg" width={18} height={18} alt="" />}#{i + 1}</td>
                <td>{n.name}</td>
                <td>{n.cpu_cores}c</td>
                <td>{n.ram_gb}GB</td>
                <td>{n.storage_gb}GB</td>
                <td>{n.base_score}</td>
                <td>{n.task_score}</td>
                <td><strong>{Math.round(n.total_score)}</strong></td>
                <td style={{ color: 'var(--yellow)', display:'flex', alignItems:'center', gap:4 }}><img src="/icons/morm-token-sm.svg" width={16} height={16} alt="" />{(n.task_score / 100).toFixed(2)}</td>
                <td className="text-sm" style={{ fontFamily: 'monospace' }}>{n.wallet_address ? `${n.wallet_address.slice(0, 6)}...${n.wallet_address.slice(-4)}` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

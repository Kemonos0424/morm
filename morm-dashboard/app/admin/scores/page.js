import { dbAll } from '@/app/lib/db';
import { unitsToMorm } from '@/app/lib/morm-units';
import { ensureNodeEmissionSchema } from '@/app/lib/node-emission';

export const dynamic = 'force-dynamic';

function fmtMorm(v) {
  const s = Number(v || 0).toFixed(6);
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s;
}

export default async function ScoresPage() {
  const nodes = await dbAll('SELECT * FROM nodes ORDER BY total_score DESC');

  // Confirmed emitted MORM per node — SAME source of truth the user page reads
  // (node_emissions, status='sent'). Guarantees admin ↔ user figures match.
  await ensureNodeEmissionSchema();
  const emitRows = await dbAll(
    `SELECT node_id, COALESCE(SUM(units),0) AS units
       FROM node_emissions WHERE status='sent' GROUP BY node_id`
  );
  const confirmedByNode = {};
  for (const r of emitRows) confirmedByNode[r.node_id] = unitsToMorm(Number(r.units || 0));

  return (
    <div>
      <h1>スコアボード</h1>
      <div className="card">
        <table>
          <thead>
            <tr><th>ランク</th><th>ノード</th><th>CPU</th><th>RAM</th><th>Storage</th><th>ベース</th><th>タスク</th><th>合計</th><th>獲得MORM(確定)</th><th>ウォレット</th></tr>
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
                <td style={{ color: 'var(--yellow)', display:'flex', alignItems:'center', gap:4 }}><img src="/icons/morm-token-sm.svg" width={16} height={16} alt="" />{fmtMorm(confirmedByNode[n.id] || 0)}</td>
                <td className="text-sm" style={{ fontFamily: 'monospace' }}>{n.wallet_address ? `${n.wallet_address.slice(0, 6)}...${n.wallet_address.slice(-4)}` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

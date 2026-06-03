import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export default async function RewardsHistoryPage() {
  const snapshots = await dbAll(`
    SELECT ws.*, n.name as node_name, n.wallet_address
    FROM weekly_snapshots ws
    JOIN nodes n ON ws.node_id = n.id
    ORDER BY ws.created_at DESC
  `);

  return (
    <div>
      <h1>MORM配布履歴</h1>
      <div className="card">
        <table>
          <thead>
            <tr><th>週</th><th>ノード</th><th>ウォレット</th><th>スコア</th><th>MORM</th><th>TX</th><th>ステータス</th></tr>
          </thead>
          <tbody>
            {snapshots.map(s => {
              const sent = s.status === 'distributed' || s.status === 'sent';
              return (
              <tr key={s.id}>
                <td style={{fontSize:12}}>{s.week_label}</td>
                <td>{s.node_name}</td>
                <td style={{fontSize:11,fontFamily:'monospace'}}>{s.wallet_address ? `${s.wallet_address.slice(0,6)}...${s.wallet_address.slice(-4)}` : '-'}</td>
                <td>{s.total_score}</td>
                <td style={{color:'var(--yellow)',fontWeight:700}}>{Number(s.morm_amount).toFixed(2)} MORM</td>
                <td style={{fontSize:11,fontFamily:'monospace'}}>{s.tx_hash ? `${s.tx_hash.slice(0,10)}...` : '-'}</td>
                <td><span className={`badge ${sent ? 'green' : s.status === 'pending' ? 'yellow' : 'red'}`}>{sent ? '配布済' : '未配布'}</span></td>
              </tr>
              );
            })}
            {snapshots.length === 0 && <tr><td colSpan={7} style={{color:'var(--muted)',textAlign:'center'}}>履歴なし</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

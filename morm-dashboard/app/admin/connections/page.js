import { dbAll } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

const SERVICES = ['x', 'instagram', 'tiktok', 'facebook', 'youtube', 'gmail', 'git', 'cloudflare'];
const SVC_NAMES = { x: 'X', instagram: 'IG', tiktok: 'TT', facebook: 'FB', youtube: 'YT', gmail: 'Gmail', git: 'GitHub', cloudflare: 'CF' };

export default async function ConnectionsPage() {
  const nodes = await dbAll('SELECT * FROM nodes ORDER BY total_score DESC');
  const connections = await dbAll('SELECT * FROM connections');

  return (
    <div>
      <h1>接続管理</h1>
      <div className="card" style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th>ノード</th>
              {SERVICES.map(s => {
                const svcIconMap = {x:'svc-x',instagram:'svc-instagram',tiktok:'svc-tiktok',facebook:'svc-facebook',youtube:'svc-youtube',gmail:'svc-gmail',git:'svc-github',cloudflare:'svc-cloudflare'};
                return <th key={s} style={{textAlign:'center'}}><div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4}}><img src={`/icons/${svcIconMap[s]}.svg`} width={20} height={20} alt="" /><span style={{fontSize:11}}>{SVC_NAMES[s]}</span></div></th>;
              })}
            </tr>
          </thead>
          <tbody>
            {nodes.map(n => (
              <tr key={n.id}>
                <td><strong>{n.name}</strong></td>
                {SERVICES.map(s => {
                  const conn = connections.find(c => c.node_id === n.id && c.service === s);
                  const ok = conn && conn.status === 'connected';
                  return (
                    <td key={s} style={{ textAlign: 'center' }}>
                      <span className={`badge ${ok ? 'green' : 'red'}`}>
                        {ok ? '接続済' : '未接続'}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

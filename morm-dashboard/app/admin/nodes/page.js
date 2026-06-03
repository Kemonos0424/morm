'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import HelpButton from '@/app/components/HelpButton';

export default function NodesPage() {
  const [nodes, setNodes] = useState([]);

  useEffect(() => {
    fetch('/api/nodes').then(r => r.json()).then(d => setNodes(Array.isArray(d) ? d : d.nodes || []));
  }, []);

  function getMethodBadge(method) {
    const colors = { SSH: 'green', Tailscale: 'purple', WireGuard: 'yellow', LAN: 'cyan', Local: 'purple' };
    const connMap = {SSH:'conn-ssh',Tailscale:'conn-tailscale',WireGuard:'conn-wireguard',LAN:'conn-local',Local:'conn-local'};
    const icon = connMap[method];
    return <span className={`badge ${colors[method] || 'blue'}`} style={{ marginRight: 4, display:'inline-flex', alignItems:'center', gap:4 }}>{icon && <img src={`/icons/${icon}.svg`} width={14} height={14} alt="" />}{method}</span>;
  }

  function showAgent(n) {
    const url = typeof window !== 'undefined' ? window.location.origin : 'https://node-dashboard-rouge.vercel.app';
    const token = n.agent_token || '(migration v5 未適用)';
    const setup = `# ${n.name} エージェント設定\nexport DASHBOARD_URL=${url}\nexport NODE_ID=${n.id}\nexport AGENT_TOKEN=${token}\nexport INTERVAL=30\nbash scripts/agent/node-agent.sh`;
    if (navigator.clipboard) navigator.clipboard.writeText(setup).catch(() => {});
    alert(setup + '\n\n(クリップボードにコピーしました)');
  }

  async function checkSpecs(nodeId) {
    try {
      const res = await fetch('/api/admin/specs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodeId })
      });
      const data = await res.json();
      if (data.specs) {
        alert(`CPU: ${data.specs.cpu_cores}コア\nRAM: ${data.specs.ram_gb}GB\nStorage: ${data.specs.storage_gb}GB`);
      } else {
        alert(data.error || 'スペック取得に失敗');
      }
      fetch('/api/nodes').then(r => r.json()).then(d => setNodes(Array.isArray(d) ? d : d.nodes || []));
    } catch {
      alert('通信エラー');
    }
  }

  return (
    <div style={{position:'relative'}}>
      <img src="/icons/network-map-bg.svg" alt="" style={{position:'absolute',top:0,right:0,width:200,opacity:0.08,pointerEvents:'none'}} />
      <div className="flex-between mb-2">
        <h1 style={{display:'flex',alignItems:'center'}}>ノード管理 <HelpButton title="ノード管理について"><p>ここでPCノードの一覧を確認・管理できます。</p><p>「+ ノード追加」でSSH情報を入力して新しいPCを登録できます。</p><p>「SSH Spec Check」でリモートPCのスペックを取得・更新できます。</p><p>ステータスが「オンライン」のノードは接続中です。</p><p>スコアはCPU x 10 + RAM x 5 + Storage x 0.1で計算されます。</p></HelpButton></h1>
        <Link href="/admin/nodes/new" className="btn btn-primary">+ ノード追加</Link>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>ID</th><th>ノード名</th><th>ステータス</th><th>スペック</th><th>接続方法</th><th>スコア</th><th>操作</th></tr>
          </thead>
          <tbody>
            {nodes.map(n => {
              let methods = [];
              try { methods = JSON.parse(n.connection_methods || '[]'); } catch {}
              return (
                <tr key={n.id}>
                  <td>{n.id}</td>
                  <td style={{display:'flex',alignItems:'center',gap:6}}><img src={/mac|mini/i.test(n.name) ? '/icons/macmini-icon.svg' : '/icons/pc-icon.svg'} width={20} height={20} alt="" />{n.name}</td>
                  <td><img src={n.status === 'online' ? '/icons/status-online.svg' : '/icons/status-offline.svg'} width={18} height={18} alt={n.status} title={n.status} /></td>
                  <td className="text-sm">{n.cpu_cores}c / {n.ram_gb}GB / {n.storage_gb}GB</td>
                  <td>{methods.map((m, i) => <span key={i}>{getMethodBadge(m)}</span>)}</td>
                  <td><strong>{Math.round(n.total_score)}</strong></td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn-sm btn-primary" onClick={() => checkSpecs(n.id)}>SSH Spec Check</button>
                      <button className="btn-sm" style={{ border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--text)' }} onClick={() => showAgent(n)}>エージェント設定</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

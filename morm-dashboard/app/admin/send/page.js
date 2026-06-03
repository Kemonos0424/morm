'use client';

import { useState, useEffect } from 'react';
import HelpButton from '@/app/components/HelpButton';

export default function SendPage() {
  const [nodes, setNodes] = useState([]);
  const [selected, setSelected] = useState({});
  const [amounts, setAmounts] = useState({});
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState('');

  useEffect(() => {
    fetch('/api/nodes').then(r => r.json()).then(d => { const arr = Array.isArray(d) ? d : d.nodes || []; setNodes(arr.filter(n => n.wallet_address)); });
  }, []);

  function toggleNode(id) {
    setSelected(prev => ({ ...prev, [id]: !prev[id] }));
  }

  function selectAll() {
    const allSelected = nodes.every(n => selected[n.id]);
    const next = {};
    nodes.forEach(n => { next[n.id] = !allSelected; });
    setSelected(next);
  }

  function calcFromScore() {
    const next = {};
    nodes.forEach(n => {
      if (selected[n.id]) {
        next[n.id] = (n.task_score / 100).toFixed(2);
      }
    });
    setAmounts(prev => ({ ...prev, ...next }));
  }

  async function handleSend() {
    const recipients = nodes
      .filter(n => selected[n.id] && amounts[n.id] > 0)
      .map(n => ({ nodeId: n.id, address: n.wallet_address, amount: parseFloat(amounts[n.id]) }));

    if (recipients.length === 0) { alert('送信先を選択してください'); return; }
    setSending(true);
    setResult('');
    try {
      const res = await fetch('/api/admin/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipients })
      });
      const data = await res.json();
      setResult(data.message || JSON.stringify(data));
    } catch {
      setResult('送信エラー');
    }
    setSending(false);
  }

  return (
    <div>
      <h1 style={{display:'flex',alignItems:'center',gap:8}}><img src="/icons/morm-token.svg" width={32} height={32} alt="" />MORM送信 <HelpButton title="MORMトークン送信について"><p>ウォレット登録済みのノードに MORM（m0r）トークンを一括送信できます。</p><p>チェックボックスで送信先を選択し、MORM量を入力してください。</p><p>「スコアから計算」でタスクスコアに基づいて MORM量を自動算出します（100スコア = 1 MORM）。</p><p>MORM L1 上で動作します。</p></HelpButton></h1>

      <div className="flex gap-1 mb-2">
        <button className="btn-sm btn-primary" onClick={selectAll}>全選択/解除</button>
        <button className="btn-sm btn-yellow" onClick={calcFromScore}>スコアから計算</button>
        <button className="btn-green" onClick={handleSend} disabled={sending}>
          {sending ? '送信中...' : '送信実行'}
        </button>
      </div>

      {result && <div className="alert success mb-2">{result}</div>}

      <div className="card">
        <table>
          <thead>
            <tr><th></th><th>ノード</th><th>ウォレット</th><th>スコア</th><th>MORM量</th></tr>
          </thead>
          <tbody>
            {nodes.map(n => (
              <tr key={n.id}>
                <td>
                  <input type="checkbox" checked={!!selected[n.id]} onChange={() => toggleNode(n.id)} />
                </td>
                <td>{n.name}</td>
                <td className="text-sm" style={{ fontFamily: 'monospace' }}>{n.wallet_address.slice(0, 10)}...{n.wallet_address.slice(-4)}</td>
                <td>{n.total_score}</td>
                <td>
                  <input
                    type="number"
                    step="0.01"
                    value={amounts[n.id] || ''}
                    onChange={e => setAmounts(prev => ({ ...prev, [n.id]: e.target.value }))}
                    style={{ width: 100, padding: '0.3rem', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text)' }}
                  />
                </td>
              </tr>
            ))}
            {nodes.length === 0 && <tr><td colSpan={5} className="text-muted text-center">ウォレット接続済みのノードなし</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

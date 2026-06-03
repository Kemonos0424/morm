'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function NewNodePage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: '', ssh_host: '', ssh_port: 22, ssh_user: '', ssh_pass: '' });
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      const res = await fetch('/api/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      const data = await res.json();
      if (res.ok) {
        router.push('/admin/nodes');
      } else {
        setError(data.error || '登録に失敗しました');
      }
    } catch {
      setError('通信エラー');
    }
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <h1>ノード追加</h1>
      <form onSubmit={handleSubmit} className="card">
        <div className="form-group">
          <label>ノード名</label>
          <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
        </div>
        <div className="form-group">
          <label>SSHホスト</label>
          <input value={form.ssh_host} onChange={e => setForm({ ...form, ssh_host: e.target.value })} placeholder="192.168.1.100" />
        </div>
        <div className="grid-2">
          <div className="form-group">
            <label>ポート</label>
            <input type="number" value={form.ssh_port} onChange={e => setForm({ ...form, ssh_port: parseInt(e.target.value) })} />
          </div>
          <div className="form-group">
            <label>ユーザー名</label>
            <input value={form.ssh_user} onChange={e => setForm({ ...form, ssh_user: e.target.value })} />
          </div>
        </div>
        <div className="form-group">
          <label>パスワード</label>
          <input type="password" value={form.ssh_pass} onChange={e => setForm({ ...form, ssh_pass: e.target.value })} />
        </div>
        {error && <p style={{ color: 'var(--red)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{error}</p>}
        <button className="btn-primary" style={{ width: '100%' }}>登録</button>
      </form>
    </div>
  );
}

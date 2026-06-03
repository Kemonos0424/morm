'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AdminLogin() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const router = useRouter();

  async function handleLogin(e) {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/auth/admin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        localStorage.setItem('admin_auth', 'true');
        router.push('/admin/dashboard');
      } else {
        setError(data.error || 'ログインに失敗しました');
      }
    } catch {
      setError('通信エラー');
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '4rem auto', textAlign: 'center' }}>
      <h1>管理者ログイン</h1>
      <form onSubmit={handleLogin} className="card mt-2">
        <div className="form-group">
          <label>パスワード</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        {error && <p style={{ color: 'var(--red)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{error}</p>}
        <button className="btn-primary" style={{ width: '100%' }}>ログイン</button>
      </form>
    </div>
  );
}

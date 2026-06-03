'use client';

import { useState, useEffect } from 'react';
import HelpButton from '@/app/components/HelpButton';

const CATEGORIES = [
  { id: 'site', name: 'Webサイト' },
  { id: 'sns', name: 'SNS' },
  { id: 'gmail', name: 'Gmail' },
  { id: 'git', name: 'Git' },
  { id: 'cloudflare', name: 'Cloudflare' },
  { id: 'automation', name: '自動化' },
  { id: 'api', name: 'API' },
  { id: 'p2p', name: 'P2P' },
  { id: 'storage', name: 'ストレージ' },
  { id: 'review', name: 'レビュー' },
];

const TRIGGERS = [
  { id: '', name: 'なし (手動)' },
  { id: 'on_connect', name: 'ノード接続時' },
  { id: 'on_schedule', name: 'スケジュール' },
];

const CREDENTIALS = [
  { id: '', name: '不要' },
  { id: 'x', name: 'X (Twitter)' },
  { id: 'instagram', name: 'Instagram' },
  { id: 'tiktok', name: 'TikTok' },
  { id: 'facebook', name: 'Facebook' },
  { id: 'youtube', name: 'YouTube' },
  { id: 'gmail', name: 'Gmail' },
  { id: 'git', name: 'Git' },
  { id: 'cloudflare', name: 'Cloudflare' },
  { id: 'custom', name: 'カスタム' },
];

const catName = id => CATEGORIES.find(c => c.id === id)?.name || id;

const defaultForm = { id: '', category: 'site', name: '', description: '', score_value: 10, auto: 0, morm_cost: 0, requires_credential: '', auto_trigger: '', cooldown_hours: 0, command: '', timeout_sec: 300 };

export default function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState({ ...defaultForm });
  const [msg, setMsg] = useState('');
  const [filter, setFilter] = useState('all');

  useEffect(() => { fetchTasks(); }, []);

  async function fetchTasks() {
    const res = await fetch('/api/tasks');
    const data = await res.json();
    setTasks(data.tasks || []);
  }

  function openNew() {
    setForm({ ...defaultForm });
    setEditMode(false);
    setShowForm(true);
    setMsg('');
  }

  function openEdit(task) {
    setForm({
      id: task.id,
      category: task.category,
      name: task.name,
      description: task.description || '',
      score_value: task.score_value,
      auto: task.auto || 0,
      morm_cost: task.morm_cost || 0,
      requires_credential: task.requires_credential || '',
      auto_trigger: task.auto_trigger || '',
      cooldown_hours: task.cooldown_hours || 0,
      command: task.command || '',
      timeout_sec: task.timeout_sec || 300,
    });
    setEditMode(true);
    setShowForm(true);
    setMsg('');
  }

  async function saveTask(e) {
    e.preventDefault();
    setMsg('');
    const method = editMode ? 'PUT' : 'POST';
    const res = await fetch('/api/tasks', {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    });
    const data = await res.json();
    if (data.success) {
      setShowForm(false);
      fetchTasks();
      setMsg(editMode ? 'タスクを更新しました' : 'タスクを追加しました');
    } else {
      setMsg('エラー: ' + (data.error || '不明'));
    }
  }

  async function deleteTask(id) {
    if (!confirm(`タスク "${id}" を削除しますか？\n関連する実行履歴も削除されます。`)) return;
    const res = await fetch(`/api/tasks?id=${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      fetchTasks();
      setMsg('タスクを削除しました');
    } else {
      setMsg('エラー: ' + (data.error || '不明'));
    }
  }

  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.category === filter);
  const grouped = {};
  filtered.forEach(t => { if (!grouped[t.category]) grouped[t.category] = []; grouped[t.category].push(t); });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ margin: 0, display:'flex', alignItems:'center' }}>タスク管理 ({tasks.length}) <HelpButton title="タスク管理について"><p>タスクはノードが実行できる作業の定義です。</p><p>「+ タスク追加」で新しいタスクを作成できます。</p><p>各タスクには獲得スコア、MORM消費量、必要アカウント等を設定可能です。</p><p><strong>自動実行トリガー:</strong> 「ノード接続時」= PC接続で自動実行、「スケジュール」= 定期実行</p><p><strong>MORM消費:</strong> 一部のタスクは MORM（m0r）トークンを消費します（残高不足だと実行不可）。</p><p><strong>必要アカウント:</strong> SNS等のログイン情報が事前登録されている必要があります。</p></HelpButton></h1>
        <button onClick={openNew} style={{
          background: 'linear-gradient(135deg,#667eea,#764ba2)', color: '#fff',
          border: 'none', borderRadius: 8, padding: '10px 20px', cursor: 'pointer', fontWeight: 600, fontSize: 14
        }}>+ タスク追加</button>
      </div>

      {msg && <div style={{ padding: '10px 16px', borderRadius: 8, marginBottom: 16, background: msg.includes('エラー') ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)', color: msg.includes('エラー') ? '#ef4444' : '#22c55e', fontSize: 14 }}>{msg}</div>}

      {/* Category filter */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        <button onClick={() => setFilter('all')} style={{
          padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, cursor: 'pointer',
          background: filter === 'all' ? 'linear-gradient(135deg,#667eea,#764ba2)' : 'var(--card)',
          color: filter === 'all' ? '#fff' : 'var(--text-muted)', fontWeight: filter === 'all' ? 600 : 400,
        }}>全て ({tasks.length})</button>
        {CATEGORIES.map(c => {
          const count = tasks.filter(t => t.category === c.id).length;
          if (count === 0) return null;
          return (
            <button key={c.id} onClick={() => setFilter(c.id)} style={{
              padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, cursor: 'pointer',
              background: filter === c.id ? 'linear-gradient(135deg,#667eea,#764ba2)' : 'var(--card)',
              color: filter === c.id ? '#fff' : 'var(--text-muted)', fontWeight: filter === c.id ? 600 : 400,
            }}>{c.name} ({count})</button>
          );
        })}
      </div>

      {/* Task table by category */}
      {Object.entries(grouped).map(([cat, items]) => (
        <div key={cat} className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <img src={`/icons/task-${cat}.svg`} width={22} height={22} alt="" onError={e => e.target.style.display = 'none'} />
            {catName(cat)}
            <span className="badge blue" style={{ fontSize: 11 }}>{items.length}</span>
          </h3>
          <table>
            <thead>
              <tr>
                <th>ID</th><th>タスク名</th><th>説明</th><th>スコア</th>
                <th>MORM</th><th>トリガー</th><th>認証</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(t => (
                <tr key={t.id}>
                  <td style={{ fontSize: 12, fontFamily: 'monospace' }}>{t.id}</td>
                  <td><strong>{t.name}</strong>{t.command && t.command.trim() ? <span className="badge blue" style={{ fontSize: 9, marginLeft: 6 }} title={t.command}>⚙ ノード実行</span> : null}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 13 }}>{t.description}</td>
                  <td style={{ fontWeight: 700, color: '#22c55e' }}>+{t.score_value}</td>
                  <td>{t.morm_cost > 0 ? <span style={{ color: '#667eea', fontWeight: 600 }}>{t.morm_cost} MORM</span> : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                  <td>{t.auto_trigger ? <span className="badge blue" style={{ fontSize: 10 }}>{t.auto_trigger}</span> : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>手動</span>}</td>
                  <td>{t.requires_credential ? <span className="badge yellow" style={{ fontSize: 10 }}>{t.requires_credential}</span> : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>不要</span>}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={() => openEdit(t)} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--text)', cursor: 'pointer' }}>編集</button>
                      <button onClick={() => deleteTask(t.id)} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)', color: '#ef4444', cursor: 'pointer' }}>削除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {filtered.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          タスクがありません
        </div>
      )}

      {/* Add/Edit Modal */}
      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
          onClick={() => setShowForm(false)}>
          <div className="card" style={{ maxWidth: 550, width: '100%', padding: 28, maxHeight: '90vh', overflowY: 'auto', background: 'var(--card-solid)', border: '1px solid var(--border)' }}
            onClick={e => e.stopPropagation()}>
            <h2 style={{ marginBottom: 16 }}>{editMode ? 'タスク編集' : '新規タスク追加'}</h2>

            <form onSubmit={saveTask}>
              <div className="form-group">
                <label>タスクID (英数字、変更不可)</label>
                <input value={form.id} onChange={e => setForm({ ...form, id: e.target.value })}
                  placeholder="例: sns_auto_reply" required disabled={editMode} style={{ opacity: editMode ? 0.5 : 1 }} />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label>カテゴリ</label>
                  <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                    {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>タスク名</label>
                  <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="例: SNS自動リプライ" required />
                </div>
              </div>

              <div className="form-group">
                <label>説明</label>
                <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="タスクの説明" />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label>獲得スコア</label>
                  <input type="number" value={form.score_value} onChange={e => setForm({ ...form, score_value: parseInt(e.target.value) || 0 })} min="0" />
                </div>
                <div className="form-group">
                  <label>MORM消費量</label>
                  <input type="number" step="0.1" value={form.morm_cost} onChange={e => setForm({ ...form, morm_cost: parseFloat(e.target.value) || 0 })} min="0" />
                </div>
                <div className="form-group">
                  <label>クールダウン (時間)</label>
                  <input type="number" value={form.cooldown_hours} onChange={e => setForm({ ...form, cooldown_hours: parseInt(e.target.value) || 0 })} min="0" />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label>自動実行トリガー</label>
                  <select value={form.auto_trigger} onChange={e => setForm({ ...form, auto_trigger: e.target.value })}>
                    {TRIGGERS.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>必要アカウント</label>
                  <select value={form.requires_credential} onChange={e => setForm({ ...form, requires_credential: e.target.value })}>
                    {CREDENTIALS.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>自動実行</label>
                  <select value={form.auto} onChange={e => setForm({ ...form, auto: parseInt(e.target.value) })}>
                    <option value={0}>手動</option>
                    <option value={1}>自動</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>実行コマンド (ノードエージェントが実行)</label>
                <textarea value={form.command} onChange={e => setForm({ ...form, command: e.target.value })}
                  placeholder="例: sudo systemctl reload nginx&#10;空欄ならノード実行なし(接続トグル等の即時タスク)" rows={3}
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: 13, resize: 'vertical' }} />
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  コマンドを設定すると、実行はノードエージェントの<strong>実行待ちキュー</strong>に入り、成功報告後にスコア/MORMが確定します。空欄のタスクは従来通り即時完了します。
                </div>
              </div>

              {form.command && form.command.trim() && (
                <div className="form-group" style={{ maxWidth: 220 }}>
                  <label>タイムアウト (秒)</label>
                  <input type="number" value={form.timeout_sec} onChange={e => setForm({ ...form, timeout_sec: parseInt(e.target.value) || 300 })} min="1" />
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <button type="submit" style={{
                  flex: 1, padding: '12px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 14,
                  background: 'linear-gradient(135deg,#667eea,#764ba2)', color: '#fff'
                }}>
                  {editMode ? '更新' : '追加'}
                </button>
                <button type="button" onClick={() => setShowForm(false)} style={{
                  padding: '12px 20px', borderRadius: 8, border: '1px solid var(--border)',
                  background: 'var(--card)', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 14
                }}>キャンセル</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

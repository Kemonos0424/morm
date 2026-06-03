'use client';

import { useState, useEffect } from 'react';
import HelpButton from '@/app/components/HelpButton';

const AD_FORMATS = [
  { ad_type: 'popunder', name: 'Popunder', description: 'ユーザーがクリックした際にバックグラウンドで開く全画面広告。最も高収益。', icon: '💰' },
  { ad_type: 'social_bar', name: 'Social Bar', description: '通知風の小さな広告。ユーザー体験を邪魔しない。', icon: '🔔' },
  { ad_type: 'banner_728', name: 'Banner 728x90', description: 'ヘッダー/フッター用の標準バナー。', icon: '📐' },
  { ad_type: 'banner_300', name: 'Banner 300x250', description: 'サイドバー/記事中用のレクタングル。', icon: '🖼' },
  { ad_type: 'native', name: 'Native Banner', description: '記事に馴染むネイティブ広告。', icon: '📰' },
  { ad_type: 'direct_link', name: 'Direct Link', description: '任意のリンクに設置。クリック報酬。', icon: '🔗' },
];

const PLACEMENT_OPTIONS = [
  { value: 'all', label: '全ページ' },
  { value: 'header', label: 'ヘッダー' },
  { value: 'footer', label: 'フッター' },
  { value: 'in-article', label: '記事中' },
  { value: 'sidebar', label: 'サイドバー' },
];

export default function AdsPage() {
  const [ads, setAds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [applyingAll, setApplyingAll] = useState(false);
  const [msg, setMsg] = useState('');

  // Local state for editing each ad format
  const [localState, setLocalState] = useState({});

  useEffect(() => {
    fetchAds();
  }, []);

  async function fetchAds() {
    try {
      const res = await fetch('/api/admin/ads');
      const data = await res.json();
      const adMap = {};
      (data.ads || []).forEach(a => { adMap[a.ad_type] = a; });
      setAds(adMap);

      // Initialize local state from DB
      const ls = {};
      AD_FORMATS.forEach(f => {
        const existing = adMap[f.ad_type];
        ls[f.ad_type] = {
          ad_code: existing ? existing.ad_code : '',
          enabled: existing ? !!existing.enabled : false,
          placement: existing ? existing.placement : 'all',
        };
      });
      setLocalState(ls);
    } catch (e) {
      console.error('Failed to fetch ads:', e);
    } finally {
      setLoading(false);
    }
  }

  function updateLocal(adType, field, value) {
    setLocalState(prev => ({
      ...prev,
      [adType]: { ...prev[adType], [field]: value },
    }));
  }

  async function saveAd(adType) {
    setSaving(prev => ({ ...prev, [adType]: true }));
    setMsg('');
    try {
      const local = localState[adType];
      const existing = ads[adType];

      if (existing) {
        // Update
        const res = await fetch('/api/admin/ads', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            id: existing.id,
            ad_code: local.ad_code,
            enabled: local.enabled ? 1 : 0,
          }),
        });
        if (!res.ok) throw new Error('Update failed');
      } else {
        // Create
        const res = await fetch('/api/admin/ads', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ad_type: adType,
            ad_code: local.ad_code,
            placement: local.placement,
            enabled: local.enabled ? 1 : 0,
          }),
        });
        if (!res.ok) throw new Error('Create failed');
      }

      setMsg(`${adType} を保存しました`);
      await fetchAds();
    } catch (e) {
      setMsg(`エラー: ${e.message}`);
    } finally {
      setSaving(prev => ({ ...prev, [adType]: false }));
    }
  }

  async function applyAll() {
    setApplyingAll(true);
    setMsg('');
    try {
      // Save all enabled ads first
      for (const f of AD_FORMATS) {
        const local = localState[f.ad_type];
        if (local.enabled && local.ad_code) {
          await saveAd(f.ad_type);
        }
      }
      setMsg('全サイトへの適用設定を保存しました。次回サイト生成時に反映されます。');
    } catch (e) {
      setMsg(`エラー: ${e.message}`);
    } finally {
      setApplyingAll(false);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'rgba(255,255,255,0.5)' }}>
        読み込み中...
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem 1rem', maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{
              fontSize: '1.8rem',
              fontWeight: 800,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              marginBottom: '0.3rem',
              display: 'flex',
              alignItems: 'center',
            }}>
              広告管理 (Adsterra) <HelpButton title="広告管理 (Adsterra) について"><p>Adsterraの広告コードを管理・設定するページです。</p><p>各広告フォーマット（Popunder, Social Bar, Banner等）のコードを登録できます。</p><p>登録したコードはサイト生成時に自動挿入されます。</p><p><strong>配置:</strong> ヘッダー、フッター、記事中、サイドバーから選択可能です。</p><p>Adsterraのダッシュボードで広告コードを取得してください。</p><p>「全サイトに適用」で既存サイトにも一括適用可能です。</p></HelpButton>
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.9rem' }}>
              各広告フォーマットのコードを設定し、生成サイトに自動挿入します。
            </p>
          </div>
          <a
            href="https://beta.publishers.adsterra.com/websites"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.6rem 1.2rem',
              background: 'linear-gradient(135deg, #667eea, #764ba2)',
              color: '#fff',
              borderRadius: '8px',
              fontSize: '0.85rem',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            Adsterra Dashboard
          </a>
        </div>
        <div style={{
          marginTop: '1rem',
          padding: '1rem',
          background: 'rgba(102, 126, 234, 0.08)',
          border: '1px solid rgba(102, 126, 234, 0.15)',
          borderRadius: '10px',
          fontSize: '0.85rem',
          color: 'rgba(255,255,255,0.6)',
          lineHeight: 1.6,
        }}>
          Adsterraで取得した広告コード（Script/HTML）を各フォーマットに貼り付けてください。
          サイト生成時に自動で適切な位置に挿入されます。
        </div>
      </div>

      {/* Status message */}
      {msg && (
        <div style={{
          padding: '0.8rem 1rem',
          marginBottom: '1.5rem',
          borderRadius: '8px',
          background: msg.startsWith('エラー') ? 'rgba(255,80,80,0.12)' : 'rgba(0,200,100,0.12)',
          border: `1px solid ${msg.startsWith('エラー') ? 'rgba(255,80,80,0.3)' : 'rgba(0,200,100,0.3)'}`,
          color: msg.startsWith('エラー') ? '#ff6b6b' : '#69db7c',
          fontSize: '0.85rem',
        }}>
          {msg}
        </div>
      )}

      {/* Ad format cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
        gap: '1.5rem',
        marginBottom: '2rem',
      }}>
        {AD_FORMATS.map(format => {
          const local = localState[format.ad_type] || { ad_code: '', enabled: false, placement: 'all' };
          const isSaving = saving[format.ad_type];

          return (
            <div key={format.ad_type} style={{
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${local.enabled ? 'rgba(102, 126, 234, 0.3)' : 'rgba(255,255,255,0.08)'}`,
              borderRadius: '16px',
              padding: '1.5rem',
              transition: 'border-color 0.2s',
            }}>
              {/* Card header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.8rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span style={{ fontSize: '1.5rem' }}>{format.icon}</span>
                  <div>
                    <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>{format.name}</h3>
                    <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.35)' }}>{format.ad_type}</span>
                  </div>
                </div>
                {/* Toggle */}
                <button
                  onClick={() => updateLocal(format.ad_type, 'enabled', !local.enabled)}
                  style={{
                    width: 48,
                    height: 26,
                    borderRadius: 13,
                    border: 'none',
                    cursor: 'pointer',
                    background: local.enabled ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.12)',
                    position: 'relative',
                    transition: 'background 0.2s',
                  }}
                >
                  <div style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    background: '#fff',
                    position: 'absolute',
                    top: 3,
                    left: local.enabled ? 25 : 3,
                    transition: 'left 0.2s',
                  }} />
                </button>
              </div>

              <p style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)', marginBottom: '1rem', lineHeight: 1.5 }}>
                {format.description}
              </p>

              {/* Ad code textarea */}
              <label style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', display: 'block', marginBottom: '0.3rem' }}>
                広告コード
              </label>
              <textarea
                value={local.ad_code}
                onChange={e => updateLocal(format.ad_type, 'ad_code', e.target.value)}
                placeholder="Adsterraから取得したコードを貼り付け..."
                rows={4}
                style={{
                  width: '100%',
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  padding: '0.7rem',
                  color: '#e0e0e0',
                  fontSize: '0.8rem',
                  fontFamily: 'monospace',
                  resize: 'vertical',
                  outline: 'none',
                }}
              />

              {/* Placement selector */}
              <div style={{ marginTop: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <label style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', whiteSpace: 'nowrap' }}>配置:</label>
                <select
                  value={local.placement}
                  onChange={e => updateLocal(format.ad_type, 'placement', e.target.value)}
                  style={{
                    flex: 1,
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '6px',
                    padding: '0.4rem 0.6rem',
                    color: '#e0e0e0',
                    fontSize: '0.8rem',
                    outline: 'none',
                  }}
                >
                  {PLACEMENT_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* Preview hint */}
              <div style={{
                marginTop: '0.8rem',
                padding: '0.5rem 0.7rem',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: '6px',
                fontSize: '0.72rem',
                color: 'rgba(255,255,255,0.3)',
              }}>
                {format.ad_type === 'popunder' && '挿入位置: </body>直前 (script)'}
                {format.ad_type === 'social_bar' && '挿入位置: </body>直前 (script)'}
                {format.ad_type === 'banner_728' && '挿入位置: <nav>の後 / </footer>の前'}
                {format.ad_type === 'banner_300' && '挿入位置: 記事サイドバー'}
                {format.ad_type === 'native' && '挿入位置: 記事間'}
                {format.ad_type === 'direct_link' && '挿入位置: リンク要素として設置'}
              </div>

              {/* Save button */}
              <button
                onClick={() => saveAd(format.ad_type)}
                disabled={isSaving}
                style={{
                  marginTop: '1rem',
                  width: '100%',
                  padding: '0.6rem',
                  background: isSaving ? 'rgba(255,255,255,0.08)' : 'linear-gradient(135deg, #667eea, #764ba2)',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: isSaving ? 'not-allowed' : 'pointer',
                  opacity: isSaving ? 0.6 : 1,
                }}
              >
                {isSaving ? '保存中...' : '保存'}
              </button>
            </div>
          );
        })}
      </div>

      {/* Bottom section */}
      <div style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '16px',
        padding: '1.5rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '0.3rem' }}>一括適用</h3>
            <p style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)' }}>
              有効な広告設定を保存し、次回のサイト生成時に全サイトへ自動適用します。
            </p>
          </div>
          <button
            onClick={applyAll}
            disabled={applyingAll}
            style={{
              padding: '0.7rem 2rem',
              background: applyingAll ? 'rgba(255,255,255,0.08)' : 'linear-gradient(135deg, #667eea, #764ba2)',
              border: 'none',
              borderRadius: '10px',
              color: '#fff',
              fontSize: '0.9rem',
              fontWeight: 700,
              cursor: applyingAll ? 'not-allowed' : 'pointer',
              opacity: applyingAll ? 0.6 : 1,
            }}
          >
            {applyingAll ? '適用中...' : '全サイトに適用'}
          </button>
        </div>

        {/* Stats placeholder */}
        <div style={{
          marginTop: '1.5rem',
          padding: '1.5rem',
          background: 'rgba(255,255,255,0.02)',
          border: '1px dashed rgba(255,255,255,0.1)',
          borderRadius: '10px',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.3)', marginBottom: '0.3rem' }}>
            広告パフォーマンス統計
          </p>
          <p style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.2)' }}>
            将来的にAdsterra API連携で表示予定
          </p>
        </div>
      </div>
    </div>
  );
}

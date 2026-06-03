'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import HelpButton from '@/app/components/HelpButton';

export default function SitesPage() {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewSite, setPreviewSite] = useState(null);

  useEffect(() => { fetchSites(); }, []);

  async function fetchSites() {
    try {
      const res = await fetch('/api/admin/sites');
      const data = await res.json();
      setSites(data.sites || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm('このサイトを削除しますか？')) return;
    try {
      await fetch(`/api/admin/sites?id=${id}`, { method: 'DELETE' });
      setSites(sites.filter(s => s.id !== id));
    } catch (e) {
      alert('削除に失敗しました');
    }
  }

  const typeBadge = (type) => {
    if (type === 'lp') return { label: 'LP', bg: '#764ba2' };
    return { label: 'ブログ', bg: '#667eea' };
  };

  const statusBadge = (status) => {
    const map = {
      draft: { label: '下書き', bg: 'rgba(255,255,255,0.1)' },
      generated: { label: '生成済', bg: '#2ecc71' },
      published: { label: '公開中', bg: '#00d2ff' },
    };
    return map[status] || map.draft;
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 700, display:'flex', alignItems:'center' }}>サイト生成 <HelpButton title="サイト生成について"><p>デザインテンプレート（67種）を選んでWebサイトを自動生成します。</p><p>「新規サイト作成」で4ステップウィザードが開始します。</p><p><strong>Step 1:</strong> テーマとキーワードを入力</p><p><strong>Step 2:</strong> デザインテンプレートを選択</p><p><strong>Step 3:</strong> AIがコンテンツを自動生成</p><p><strong>Step 4:</strong> プレビューを確認して保存</p><p>生成されたサイトはノードPCに配信して公開できます。</p></HelpButton></h1>
        <Link href="/admin/sites/new" style={{
          padding: '0.7rem 1.5rem',
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          color: '#fff',
          borderRadius: '12px',
          fontWeight: 600,
          fontSize: '0.9rem',
          textDecoration: 'none',
        }}>
          ＋ 新規サイト作成
        </Link>
      </div>

      {loading ? (
        <p style={{ color: 'rgba(255,255,255,0.5)' }}>読み込み中...</p>
      ) : sites.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '4rem 2rem',
          background: 'rgba(255,255,255,0.03)',
          borderRadius: '16px',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <p style={{ fontSize: '2rem', marginBottom: '1rem' }}>🌐</p>
          <p style={{ color: 'rgba(255,255,255,0.5)', marginBottom: '1rem' }}>サイトがまだありません</p>
          <Link href="/admin/sites/new" style={{ color: '#667eea' }}>最初のサイトを作成する →</Link>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
          gap: '1.5rem',
        }}>
          {sites.map(site => {
            const tb = typeBadge(site.site_type);
            const sb = statusBadge(site.status);
            const screenshotUrl = site.design_template
              ? `/design-md-${site.design_source || 'jp'}/${site.design_template}/preview-screenshot.png`
              : null;

            return (
              <div key={site.id} style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '16px',
                overflow: 'hidden',
                transition: 'transform 0.2s',
              }}>
                {screenshotUrl && (
                  <div style={{ height: '160px', overflow: 'hidden', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    <img src={screenshotUrl} alt={site.design_template} style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      opacity: 0.7,
                    }} />
                  </div>
                )}
                <div style={{ padding: '1.2rem' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.8rem' }}>
                    <span style={{
                      padding: '0.2rem 0.6rem',
                      background: tb.bg,
                      borderRadius: '6px',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      color: '#fff',
                    }}>{tb.label}</span>
                    <span style={{
                      padding: '0.2rem 0.6rem',
                      background: sb.bg,
                      borderRadius: '6px',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      color: '#fff',
                    }}>{sb.label}</span>
                  </div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.4rem', color: '#fff' }}>
                    {site.title}
                  </h3>
                  <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)', marginBottom: '0.3rem' }}>
                    テンプレート: {site.design_template || '未選択'} ({site.design_source || 'jp'})
                  </div>
                  {site.theme && (
                    <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)', marginBottom: '0.8rem' }}>
                      テーマ: {site.theme}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {site.html_content && (
                      <button onClick={() => setPreviewSite(site)} style={{
                        padding: '0.4rem 1rem',
                        background: 'rgba(102, 126, 234, 0.2)',
                        border: '1px solid rgba(102, 126, 234, 0.4)',
                        borderRadius: '8px',
                        color: '#667eea',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        fontWeight: 600,
                      }}>プレビュー</button>
                    )}
                    <button onClick={() => handleDelete(site.id)} style={{
                      padding: '0.4rem 1rem',
                      background: 'rgba(255, 71, 87, 0.1)',
                      border: '1px solid rgba(255, 71, 87, 0.3)',
                      borderRadius: '8px',
                      color: '#ff4757',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}>削除</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Preview Modal */}
      {previewSite && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.8)',
          backdropFilter: 'blur(8px)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          padding: '2rem',
        }} onClick={() => setPreviewSite(null)}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1rem',
          }}>
            <h3 style={{ color: '#fff', fontSize: '1.2rem' }}>{previewSite.title} - プレビュー</h3>
            <button onClick={() => setPreviewSite(null)} style={{
              background: 'rgba(255,255,255,0.1)',
              border: 'none',
              color: '#fff',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '0.9rem',
            }}>✕ 閉じる</button>
          </div>
          <div style={{ flex: 1, borderRadius: '12px', overflow: 'hidden' }} onClick={e => e.stopPropagation()}>
            <iframe
              src={`/api/admin/sites/preview?id=${previewSite.id}`}
              style={{ width: '100%', height: '100%', border: 'none', borderRadius: '12px' }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

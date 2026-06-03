'use client';
import { useState } from 'react';
import Link from 'next/link';
import HelpButton from '@/app/components/HelpButton';

const JP = ['apple','smarthr','freee','note','novasell','wired','mercari','muji','studio'];
const EN = ['stripe','vercel','notion','linear.app','figma','supabase','airbnb','spotify','claude','framer','uber','tesla','spacex','bmw','nvidia','coinbase','webflow','sentry','posthog','mongodb'];

export default function NewSitePage() {
  const [step, setStep] = useState(1);
  const [title, setTitle] = useState('');
  const [theme, setTheme] = useState('');
  const [siteType, setSiteType] = useState('blog');
  const [designSource, setDesignSource] = useState('jp');
  const [designTemplate, setDesignTemplate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [siteId, setSiteId] = useState(null);
  const [progressText, setProgressText] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [editDesc, setEditDesc] = useState('');

  const templates = designSource === 'jp' ? JP : EN;

  async function handleGenerate() {
    setGenerating(true);
    setProgressText('サイトを作成中...');
    try {
      // Step 1: Create site
      const createRes = await fetch('/api/admin/sites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          site_type: siteType,
          design_template: designTemplate,
          design_source: designSource,
          theme,
          keywords: theme,
        }),
      });
      const createData = await createRes.json();
      if (createData.error) throw new Error(createData.error);

      const newSiteId = createData.site.id;
      setSiteId(newSiteId);
      setEditTitle(title);

      setProgressText('コンテンツを生成中...');

      // Step 2: Generate content
      const genRes = await fetch('/api/admin/sites/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ site_id: newSiteId }),
      });
      const genData = await genRes.json();
      if (genData.error) throw new Error(genData.error);

      setProgressText(`生成完了！ HTML: ${genData.html_preview_length.toLocaleString()}文字 / ページ数: ${genData.pages_count}`);

      setTimeout(() => setStep(4), 1500);
    } catch (e) {
      setProgressText(`エラー: ${e.message}`);
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!siteId) return;
    try {
      // Use a simple PATCH-like approach via POST with update flag
      await fetch('/api/admin/sites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editTitle,
          meta_description: editDesc,
          site_type: siteType,
          design_template: designTemplate,
          design_source: designSource,
          theme,
          keywords: theme,
        }),
      });
      alert('保存しました');
    } catch (e) {
      alert('保存に失敗しました');
    }
  }

  const cardStyle = {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px',
    padding: '2rem',
  };

  const inputStyle = {
    width: '100%',
    padding: '0.8rem 1rem',
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: '10px',
    color: '#fff',
    fontSize: '0.95rem',
    outline: 'none',
  };

  const btnPrimary = {
    padding: '0.8rem 2rem',
    background: 'linear-gradient(135deg, #667eea, #764ba2)',
    color: '#fff',
    border: 'none',
    borderRadius: '12px',
    fontWeight: 600,
    fontSize: '0.95rem',
    cursor: 'pointer',
  };

  const btnDisabled = { ...btnPrimary, opacity: 0.4, cursor: 'not-allowed' };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <Link href="/admin/sites" style={{ color: 'rgba(255,255,255,0.5)', textDecoration: 'none' }}>← 戻る</Link>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 700, display:'flex', alignItems:'center' }}>新規サイト作成 <HelpButton title="サイト生成ウィザードについて"><p>4ステップでサイトを自動生成します。</p><p><strong>ブログ:</strong> テーマに合わせた5記事のブログサイト</p><p><strong>LP:</strong> ランディングページ（ヒーロー、特徴、CTA等）</p><p>デザインは日本語9種、英語58種から選択可能です。</p><p>生成後にプレビューで確認・編集ができます。</p></HelpButton></h1>
      </div>

      {/* Step indicators */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem' }}>
        {['基本情報', 'デザイン選択', '生成', 'プレビュー'].map((label, i) => (
          <div key={i} style={{
            flex: 1,
            padding: '0.6rem',
            textAlign: 'center',
            borderRadius: '8px',
            fontSize: '0.8rem',
            fontWeight: 600,
            background: step === i + 1 ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.04)',
            color: step === i + 1 ? '#fff' : step > i + 1 ? '#667eea' : 'rgba(255,255,255,0.3)',
            border: step > i + 1 ? '1px solid rgba(102,126,234,0.3)' : '1px solid rgba(255,255,255,0.06)',
          }}>
            {i + 1}. {label}
          </div>
        ))}
      </div>

      {/* Step 1: Basic Info */}
      {step === 1 && (
        <div style={cardStyle}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '1.5rem', fontWeight: 600 }}>基本情報</h2>

          <div style={{ marginBottom: '1.2rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '0.4rem' }}>
              サイトタイトル
            </label>
            <input
              type="text"
              style={inputStyle}
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="例: AI Tech Blog"
            />
          </div>

          <div style={{ marginBottom: '1.2rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '0.4rem' }}>
              テーマ / キーワード
            </label>
            <input
              type="text"
              style={inputStyle}
              value={theme}
              onChange={e => setTheme(e.target.value)}
              placeholder="例: AI テクノロジー"
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '0.6rem' }}>
              サイト種別
            </label>
            <div style={{ display: 'flex', gap: '1rem' }}>
              {[
                { value: 'blog', label: 'ブログ', desc: '記事一覧型サイト' },
                { value: 'lp', label: 'LP', desc: 'ランディングページ' },
              ].map(opt => (
                <label key={opt.value} style={{
                  flex: 1,
                  display: 'block',
                  padding: '1rem',
                  borderRadius: '12px',
                  border: siteType === opt.value ? '2px solid #667eea' : '1px solid rgba(255,255,255,0.1)',
                  background: siteType === opt.value ? 'rgba(102,126,234,0.1)' : 'rgba(255,255,255,0.02)',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}>
                  <input
                    type="radio"
                    name="siteType"
                    value={opt.value}
                    checked={siteType === opt.value}
                    onChange={e => setSiteType(e.target.value)}
                    style={{ display: 'none' }}
                  />
                  <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '0.3rem' }}>{opt.label}</div>
                  <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)' }}>{opt.desc}</div>
                </label>
              ))}
            </div>
          </div>

          <button
            style={title.trim() ? btnPrimary : btnDisabled}
            disabled={!title.trim()}
            onClick={() => setStep(2)}
          >
            次へ →
          </button>
        </div>
      )}

      {/* Step 2: Design Selection */}
      {step === 2 && (
        <div style={cardStyle}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', fontWeight: 600 }}>デザイン選択</h2>

          {/* JP/EN toggle */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
            {[
              { value: 'jp', label: '日本語デザイン (9)' },
              { value: 'en', label: '英語デザイン (20)' },
            ].map(tab => (
              <button key={tab.value} onClick={() => { setDesignSource(tab.value); setDesignTemplate(''); }} style={{
                padding: '0.5rem 1.2rem',
                borderRadius: '8px',
                border: 'none',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer',
                background: designSource === tab.value ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.06)',
                color: designSource === tab.value ? '#fff' : 'rgba(255,255,255,0.5)',
              }}>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Template grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: '1rem',
            marginBottom: '1.5rem',
            maxHeight: '500px',
            overflowY: 'auto',
          }}>
            {templates.map(t => (
              <div
                key={t}
                onClick={() => setDesignTemplate(t)}
                style={{
                  borderRadius: '12px',
                  overflow: 'hidden',
                  cursor: 'pointer',
                  border: designTemplate === t ? '2px solid #667eea' : '1px solid rgba(255,255,255,0.08)',
                  background: designTemplate === t ? 'rgba(102,126,234,0.1)' : 'rgba(255,255,255,0.02)',
                  transition: 'all 0.2s',
                }}
              >
                <img
                  src={`/design-md-${designSource}/${t}/preview-screenshot.png`}
                  alt={t}
                  style={{ width: '100%', height: '100px', objectFit: 'cover', opacity: designTemplate === t ? 1 : 0.6 }}
                  onError={e => { e.target.style.display = 'none'; }}
                />
                <div style={{
                  padding: '0.5rem 0.7rem',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  color: designTemplate === t ? '#667eea' : 'rgba(255,255,255,0.6)',
                  textTransform: 'capitalize',
                }}>
                  {t}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '0.8rem' }}>
            <button onClick={() => setStep(1)} style={{
              ...btnPrimary,
              background: 'rgba(255,255,255,0.08)',
            }}>← 戻る</button>
            <button
              style={designTemplate ? btnPrimary : btnDisabled}
              disabled={!designTemplate}
              onClick={() => setStep(3)}
            >
              次へ →
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Generate */}
      {step === 3 && (
        <div style={cardStyle}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '1.5rem', fontWeight: 600 }}>サイト生成</h2>

          <div style={{
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '12px',
            padding: '1.5rem',
            marginBottom: '1.5rem',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div style={{ marginBottom: '0.6rem' }}>
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem' }}>タイトル:</span>{' '}
              <span style={{ fontWeight: 600 }}>{title}</span>
            </div>
            <div style={{ marginBottom: '0.6rem' }}>
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem' }}>種別:</span>{' '}
              <span style={{ fontWeight: 600 }}>{siteType === 'blog' ? 'ブログ' : 'LP'}</span>
            </div>
            <div style={{ marginBottom: '0.6rem' }}>
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem' }}>テーマ:</span>{' '}
              <span style={{ fontWeight: 600 }}>{theme || '未設定'}</span>
            </div>
            <div>
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem' }}>テンプレート:</span>{' '}
              <span style={{ fontWeight: 600 }}>{designTemplate} ({designSource})</span>
            </div>
          </div>

          {progressText && (
            <div style={{
              padding: '1rem',
              background: progressText.includes('エラー') ? 'rgba(255,71,87,0.1)' : 'rgba(102,126,234,0.1)',
              borderRadius: '10px',
              marginBottom: '1rem',
              fontSize: '0.9rem',
              color: progressText.includes('エラー') ? '#ff4757' : progressText.includes('完了') ? '#2ecc71' : '#667eea',
              fontWeight: 600,
            }}>
              {generating && <span style={{ marginRight: '0.5rem' }}>⏳</span>}
              {progressText}
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.8rem' }}>
            <button onClick={() => setStep(2)} disabled={generating} style={{
              ...btnPrimary,
              background: 'rgba(255,255,255,0.08)',
              opacity: generating ? 0.4 : 1,
            }}>← 戻る</button>
            <button
              style={generating ? btnDisabled : btnPrimary}
              disabled={generating}
              onClick={handleGenerate}
            >
              {generating ? '生成中...' : 'サイトを生成'}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Preview */}
      {step === 4 && siteId && (
        <div style={cardStyle}>
          <h2 style={{ fontSize: '1.2rem', marginBottom: '1.5rem', fontWeight: 600 }}>プレビュー</h2>

          <div style={{
            borderRadius: '12px',
            overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.1)',
            marginBottom: '2rem',
            height: '500px',
          }}>
            <iframe
              src={`/api/admin/sites/preview?id=${siteId}`}
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>

          <div style={{
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '12px',
            padding: '1.5rem',
            marginBottom: '1.5rem',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '0.4rem' }}>
                タイトル
              </label>
              <input type="text" style={inputStyle} value={editTitle} onChange={e => setEditTitle(e.target.value)} />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', marginBottom: '0.4rem' }}>
                メタディスクリプション
              </label>
              <textarea
                style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
                value={editDesc}
                onChange={e => setEditDesc(e.target.value)}
                placeholder="サイトの説明文"
              />
            </div>
            <button style={btnPrimary} onClick={handleSave}>保存</button>
          </div>

          <Link href="/admin/sites" style={{
            display: 'inline-block',
            padding: '0.7rem 1.5rem',
            background: 'rgba(255,255,255,0.08)',
            borderRadius: '10px',
            color: '#fff',
            fontWeight: 600,
            fontSize: '0.9rem',
            textDecoration: 'none',
          }}>
            サイト一覧へ →
          </Link>
        </div>
      )}
    </div>
  );
}

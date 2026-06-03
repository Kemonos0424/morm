'use client';

import { useState } from 'react';
import HelpButton from '@/app/components/HelpButton';

const JP_DESIGNS = [
  { id: 'apple', name: 'Apple Japan', cat: 'Consumer Tech', desc: 'ミニマルで洗練されたApple日本版デザイン', color: '#1d1d1f' },
  { id: 'smarthr', name: 'SmartHR', cat: 'HR SaaS', desc: '親しみやすいHR SaaSデザイン', color: '#00c4cc' },
  { id: 'freee', name: 'freee', cat: 'Fintech SaaS', desc: 'クラウド会計の明るいUI', color: '#6559f6' },
  { id: 'note', name: 'note', cat: 'Media', desc: '読みやすさ重視の美しいタイポグラフィ', color: '#41c9b4' },
  { id: 'novasell', name: 'Novasell', cat: 'AI Agency', desc: 'AIエージェンシーのモダンデザイン', color: '#0066ff' },
  { id: 'wired', name: 'WIRED.jp', cat: 'Tech Media', desc: '力強いエディトリアルデザイン', color: '#000000' },
  { id: 'mercari', name: 'メルカリ', cat: 'Marketplace', desc: 'フリマアプリのUIデザイン', color: '#ff0211' },
  { id: 'muji', name: '無印良品', cat: 'Retail', desc: '無駄のないシンプルデザイン', color: '#b9232c' },
  { id: 'studio', name: 'Studio', cat: 'Web Builder', desc: 'ノーコードWebビルダー', color: '#5b6cf0' },
];

const EN_DESIGNS = [
  { id: 'stripe', name: 'Stripe', cat: 'Fintech', color: '#635bff' },
  { id: 'vercel', name: 'Vercel', cat: 'Platform', color: '#000000' },
  { id: 'notion', name: 'Notion', cat: 'Productivity', color: '#2e2e2e' },
  { id: 'linear.app', name: 'Linear', cat: 'Project Mgmt', color: '#5e6ad2' },
  { id: 'figma', name: 'Figma', cat: 'Design', color: '#a259ff' },
  { id: 'supabase', name: 'Supabase', cat: 'Backend', color: '#3ecf8e' },
  { id: 'airbnb', name: 'Airbnb', cat: 'Travel', color: '#ff5a5f' },
  { id: 'spotify', name: 'Spotify', cat: 'Music', color: '#1db954' },
  { id: 'claude', name: 'Claude', cat: 'AI', color: '#da7756' },
  { id: 'framer', name: 'Framer', cat: 'Web Builder', color: '#0055ff' },
  { id: 'uber', name: 'Uber', cat: 'Transport', color: '#000000' },
  { id: 'cursor', name: 'Cursor', cat: 'Dev Tool', color: '#1a1a2e' },
  { id: 'spacex', name: 'SpaceX', cat: 'Aerospace', color: '#005288' },
  { id: 'tesla', name: 'Tesla', cat: 'Automotive', color: '#cc0000' },
  { id: 'ferrari', name: 'Ferrari', cat: 'Automotive', color: '#dc0000' },
  { id: 'bmw', name: 'BMW', cat: 'Automotive', color: '#0066b1' },
  { id: 'lamborghini', name: 'Lamborghini', cat: 'Automotive', color: '#ddb321' },
  { id: 'renault', name: 'Renault', cat: 'Automotive', color: '#ffcc00' },
  { id: 'apple', name: 'Apple', cat: 'Consumer Tech', color: '#1d1d1f' },
  { id: 'nvidia', name: 'NVIDIA', cat: 'GPU/AI', color: '#76b900' },
  { id: 'pinterest', name: 'Pinterest', cat: 'Social', color: '#e60023' },
  { id: 'webflow', name: 'Webflow', cat: 'Web Builder', color: '#4353ff' },
  { id: 'miro', name: 'Miro', cat: 'Collaboration', color: '#ffd02f' },
  { id: 'sentry', name: 'Sentry', cat: 'Dev Tool', color: '#362d59' },
  { id: 'posthog', name: 'PostHog', cat: 'Analytics', color: '#1d4aff' },
  { id: 'mongodb', name: 'MongoDB', cat: 'Database', color: '#00684a' },
  { id: 'hashicorp', name: 'HashiCorp', cat: 'Infrastructure', color: '#000000' },
  { id: 'ibm', name: 'IBM', cat: 'Enterprise', color: '#0f62fe' },
  { id: 'coinbase', name: 'Coinbase', cat: 'Crypto', color: '#0052ff' },
  { id: 'kraken', name: 'Kraken', cat: 'Crypto', color: '#5741d9' },
  { id: 'revolut', name: 'Revolut', cat: 'Fintech', color: '#0075eb' },
  { id: 'wise', name: 'Wise', cat: 'Fintech', color: '#9fe870' },
  { id: 'resend', name: 'Resend', cat: 'Email', color: '#000000' },
  { id: 'raycast', name: 'Raycast', cat: 'Productivity', color: '#ff6363' },
  { id: 'warp', name: 'Warp', cat: 'Terminal', color: '#01a4ff' },
  { id: 'elevenlabs', name: 'ElevenLabs', cat: 'AI Voice', color: '#000000' },
  { id: 'replicate', name: 'Replicate', cat: 'AI', color: '#000000' },
  { id: 'ollama', name: 'Ollama', cat: 'AI', color: '#ffffff' },
  { id: 'cohere', name: 'Cohere', cat: 'AI', color: '#39594d' },
  { id: 'mistral.ai', name: 'Mistral', cat: 'AI', color: '#f54e42' },
  { id: 'together.ai', name: 'Together', cat: 'AI', color: '#0066ff' },
  { id: 'x.ai', name: 'xAI', cat: 'AI', color: '#000000' },
  { id: 'minimax', name: 'MiniMax', cat: 'AI', color: '#6366f1' },
  { id: 'opencode.ai', name: 'OpenCode', cat: 'AI', color: '#000000' },
  { id: 'lovable', name: 'Lovable', cat: 'AI Builder', color: '#ff69b4' },
  { id: 'composio', name: 'Composio', cat: 'Integration', color: '#4f46e5' },
  { id: 'expo', name: 'Expo', cat: 'Mobile Dev', color: '#000020' },
  { id: 'sanity', name: 'Sanity', cat: 'CMS', color: '#f36458' },
  { id: 'mintlify', name: 'Mintlify', cat: 'Docs', color: '#0d9373' },
  { id: 'airtable', name: 'Airtable', cat: 'Database', color: '#fcb400' },
  { id: 'clay', name: 'Clay', cat: 'Data', color: '#5046e5' },
  { id: 'clickhouse', name: 'ClickHouse', cat: 'Database', color: '#fadb14' },
  { id: 'intercom', name: 'Intercom', cat: 'Support', color: '#286efa' },
  { id: 'superhuman', name: 'Superhuman', cat: 'Email', color: '#6c5ce7' },
  { id: 'cal', name: 'Cal.com', cat: 'Scheduling', color: '#292929' },
  { id: 'runwayml', name: 'Runway', cat: 'AI Video', color: '#000000' },
  { id: 'zapier', name: 'Zapier', cat: 'Automation', color: '#ff4a00' },
  { id: 'voltagent', name: 'VoltAgent', cat: 'AI Agent', color: '#f5a623' },
];

export default function DesignsPage() {
  const [tab, setTab] = useState('jp');
  const [preview, setPreview] = useState(null);
  const [previewMode, setPreviewMode] = useState('light');
  const [search, setSearch] = useState('');

  const designs = tab === 'jp' ? JP_DESIGNS : EN_DESIGNS;
  const filtered = search ? designs.filter(d =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.cat.toLowerCase().includes(search.toLowerCase())
  ) : designs;

  const basePath = tab === 'jp' ? '/design-md-jp' : '/design-md-en';

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
        <h1 style={{margin:0,display:'flex',alignItems:'center'}}>デザインテンプレート <HelpButton title="デザインテンプレートについて"><p>DESIGN.mdベースのデザインシステム集です。</p><p><strong>日本語版（9種）:</strong> Apple Japan, SmartHR, freee, note, メルカリ等</p><p><strong>英語版（58種）:</strong> Stripe, Vercel, Tesla, SpaceX等</p><p>「プレビュー」でデザインの見た目を確認できます。</p><p>「DESIGN.md」で詳細なスタイル定義を確認できます。</p><p>サイト生成時にこれらのデザインを適用できます。</p></HelpButton></h1>
        <div style={{display:'flex',gap:4}}>
          <button onClick={()=>{setTab('jp');setSearch('')}}
            style={{padding:'8px 20px',borderRadius:8,border:'1px solid var(--border)',
              background:tab==='jp'?'linear-gradient(135deg,#667eea,#764ba2)':'var(--card)',
              color:tab==='jp'?'#fff':'var(--text-muted)',fontWeight:600,cursor:'pointer',fontSize:14}}>
            🇯🇵 日本語 ({JP_DESIGNS.length})
          </button>
          <button onClick={()=>{setTab('en');setSearch('')}}
            style={{padding:'8px 20px',borderRadius:8,border:'1px solid var(--border)',
              background:tab==='en'?'linear-gradient(135deg,#667eea,#764ba2)':'var(--card)',
              color:tab==='en'?'#fff':'var(--text-muted)',fontWeight:600,cursor:'pointer',fontSize:14}}>
            🌍 英語 ({EN_DESIGNS.length})
          </button>
        </div>
      </div>

      <div style={{marginBottom:20}}>
        <input
          value={search}
          onChange={e=>setSearch(e.target.value)}
          placeholder="デザインを検索..."
          style={{maxWidth:300}}
        />
        <span style={{marginLeft:12,color:'var(--text-muted)',fontSize:13}}>
          {filtered.length}件表示
        </span>
      </div>

      <div className="grid-3">
        {filtered.map(d => (
          <div key={d.id} className="card" style={{padding:0,overflow:'hidden',transition:'transform 0.2s'}}
            onMouseOver={e=>e.currentTarget.style.transform='translateY(-3px)'}
            onMouseOut={e=>e.currentTarget.style.transform='none'}>
            {/* Color bar */}
            <div style={{height:5,background:d.color}} />

            {/* Preview area */}
            <div style={{height:150,overflow:'hidden',background:'#111',position:'relative'}}>
              <img src={`${basePath}/${d.id}/preview-screenshot.png`} alt={d.name}
                style={{width:'100%',height:'100%',objectFit:'cover',objectPosition:'top',opacity:0.9}}
                onError={e=>{e.target.parentElement.style.background=`linear-gradient(135deg, ${d.color}22, ${d.color}44)`;e.target.style.display='none'}} />
              <div style={{position:'absolute',bottom:8,right:8}}>
                <span style={{background:'rgba(0,0,0,0.75)',color:'#fff',padding:'3px 10px',borderRadius:6,fontSize:11,fontWeight:600}}>{d.cat}</span>
              </div>
            </div>

            <div style={{padding:'14px 16px'}}>
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                <div style={{width:10,height:10,borderRadius:'50%',background:d.color,flexShrink:0,border:'1px solid rgba(255,255,255,0.1)'}} />
                <strong style={{fontSize:15}}>{d.name}</strong>
                <span style={{fontSize:11,color:'var(--text-muted)',marginLeft:'auto'}}>{d.cat}</span>
              </div>

              {d.desc && <p style={{color:'var(--text-muted)',fontSize:12,lineHeight:1.5,margin:'0 0 12px 0'}}>{d.desc}</p>}

              <div style={{display:'flex',gap:6}}>
                <button onClick={()=>{setPreview(d.id);setPreviewMode('light')}}
                  style={{flex:1,padding:'7px',borderRadius:8,border:'1px solid var(--border)',background:'var(--card)',color:'var(--text)',cursor:'pointer',fontSize:12,fontWeight:500}}>
                  プレビュー
                </button>
                <a href={`${basePath}/${d.id}/DESIGN.md`} target="_blank" rel="noopener"
                  style={{flex:1,padding:'7px',borderRadius:8,background:'linear-gradient(135deg,#667eea,#764ba2)',color:'#fff',textAlign:'center',fontSize:12,fontWeight:600,textDecoration:'none'}}>
                  DESIGN.md
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Preview modal */}
      {preview && (
        <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,background:'rgba(0,0,0,0.85)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center',padding:20}}
          onClick={()=>setPreview(null)}>
          <div style={{background:'var(--card)',borderRadius:16,maxWidth:1100,width:'100%',maxHeight:'92vh',overflow:'hidden',boxShadow:'0 25px 80px rgba(0,0,0,0.6)'}}
            onClick={e=>e.stopPropagation()}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'12px 20px',borderBottom:'1px solid var(--border)'}}>
              <div style={{display:'flex',alignItems:'center',gap:12}}>
                <strong style={{fontSize:16}}>{(tab==='jp'?JP_DESIGNS:EN_DESIGNS).find(d=>d.id===preview)?.name}</strong>
                {tab === 'en' && (
                  <div style={{display:'flex',gap:4}}>
                    <button onClick={()=>setPreviewMode('light')}
                      style={{padding:'4px 10px',borderRadius:6,fontSize:11,border:'1px solid var(--border)',
                        background:previewMode==='light'?'var(--accent)':'var(--card)',color:previewMode==='light'?'#fff':'var(--text-muted)',cursor:'pointer'}}>
                      Light
                    </button>
                    <button onClick={()=>setPreviewMode('dark')}
                      style={{padding:'4px 10px',borderRadius:6,fontSize:11,border:'1px solid var(--border)',
                        background:previewMode==='dark'?'var(--accent)':'var(--card)',color:previewMode==='dark'?'#fff':'var(--text-muted)',cursor:'pointer'}}>
                      Dark
                    </button>
                  </div>
                )}
              </div>
              <button onClick={()=>setPreview(null)} style={{background:'none',border:'none',color:'var(--text-muted)',fontSize:22,cursor:'pointer',padding:'4px 8px'}}>✕</button>
            </div>
            <iframe
              src={`${basePath}/${preview}/${previewMode==='dark'&&tab==='en'?'preview-dark.html':'preview.html'}`}
              style={{width:'100%',height:'78vh',border:'none'}}
              title="Preview"
            />
          </div>
        </div>
      )}
    </div>
  );
}

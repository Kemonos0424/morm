'use client';

import { useState, useEffect, useRef } from 'react';

const CAT_NAMES = {site:'サイト作成',sns:'SNS連携',gmail:'Gmail',git:'Git',cloudflare:'Cloudflare',automation:'自動化',api:'API連携',p2p:'P2P',storage:'ストレージ',review:'レビュー'};
const SERVICES = ['x','instagram','tiktok','facebook','youtube','gmail','git','cloudflare'];
const SVC_NAMES = {x:'X',instagram:'IG',tiktok:'TT',facebook:'FB',youtube:'YT',gmail:'Gmail',git:'GitHub',cloudflare:'CF'};

const CRED_TEMPLATES = {
  x: [{key:'api_key',label:'API Key'},{key:'api_secret',label:'API Secret'},{key:'access_token',label:'Access Token'},{key:'access_secret',label:'Access Secret'}],
  instagram: [{key:'username',label:'ユーザー名'},{key:'password',label:'パスワード'}],
  tiktok: [{key:'username',label:'ユーザー名'},{key:'password',label:'パスワード'}],
  facebook: [{key:'access_token',label:'Access Token'}],
  youtube: [{key:'api_key',label:'API Key'}],
  gmail: [{key:'email',label:'メールアドレス'},{key:'app_password',label:'アプリパスワード'}],
  git: [{key:'username',label:'ユーザー名'},{key:'token',label:'トークン'}],
  cloudflare: [{key:'api_token',label:'APIトークン'},{key:'zone_id',label:'Zone ID'}],
  custom: [{key:'key',label:'キー'},{key:'value',label:'値'}],
};

export default function MyPage() {
  const [tab, setTab] = useState('nodes');
  const [address, setAddress] = useState('');
  const [data, setData] = useState({ nodes: [], connections: [] });
  const [taskData, setTaskData] = useState({ tasks: [], runs: [] });
  const [credentials, setCredentials] = useState([]);
  const [messages, setMessages] = useState([]);
  const [unreadAdmin, setUnreadAdmin] = useState(0);
  const [loading, setLoading] = useState(true);
  const [linkId, setLinkId] = useState('');
  const [linkMsg, setLinkMsg] = useState('');
  const [execMsg, setExecMsg] = useState('');
  const [credForm, setCredForm] = useState(null);
  const [credValues, setCredValues] = useState({});
  const [chatInput, setChatInput] = useState('');
  const [chatNode, setChatNode] = useState('');
  const chatEndRef = useRef(null);

  // Profile state
  const [displayName, setDisplayName] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [editingWallet, setEditingWallet] = useState(false);
  const [walletInput, setWalletInput] = useState('');
  const [walletError, setWalletError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const addr = localStorage.getItem('wallet_address');
    if (!addr) { window.location.href = '/'; return; }
    setAddress(addr);
    const savedName = localStorage.getItem('user_display_name');
    if (savedName) setDisplayName(savedName);
    fetchAll(addr);
  }, []);

  useEffect(() => {
    if (chatEndRef.current) chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, tab]);

  async function fetchAll(addr) {
    try {
      const [nRes, tRes, cRes, mRes] = await Promise.all([
        fetch(`/api/my/nodes?address=${addr}`),
        fetch(`/api/my/tasks?address=${addr}`),
        fetch(`/api/my/credentials?address=${addr}`),
        fetch(`/api/my/messages?address=${addr}`)
      ]);
      const nData = await nRes.json();
      const tData = await tRes.json();
      const cData = await cRes.json();
      const mData = await mRes.json();
      setData({ nodes: nData.nodes || [], connections: nData.connections || [] });
      setTaskData({ tasks: tData.tasks || [], runs: tData.runs || [] });
      setCredentials(cData.credentials || []);
      const msgs = mData.messages || [];
      setMessages(msgs);
      setUnreadAdmin(msgs.filter(m => m.sender === 'admin' && !m.read).length);
      if (nData.nodes && nData.nodes.length > 0 && !chatNode) {
        setChatNode(nData.nodes[0].id);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function linkNode() {
    if (!linkId.trim()) return;
    setLinkMsg('');
    const res = await fetch('/api/my/link', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ node_id: linkId.trim(), address })
    });
    const r = await res.json();
    if (r.success || r.nodeName) {
      setLinkMsg((r.nodeName || linkId) + ' を紐づけました！');
      setLinkId('');
      fetchAll(address);
    } else {
      setLinkMsg('エラー: ' + (r.error || r.message || '不明'));
    }
  }

  async function executeTask(nodeId, taskId) {
    setExecMsg('');
    const res = await fetch('/api/my/tasks/execute', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ address, node_id: nodeId, task_id: taskId })
    });
    const r = await res.json();
    if (r.success && r.queued) {
      setExecMsg('実行待ちに追加しました。ノードでの実行完了後にスコア/MORMが反映されます。');
      fetchAll(address);
    } else if (r.success) {
      setExecMsg(`成功! +${r.score_earned}pt${r.morm_spent > 0 ? ` / -${r.morm_spent} MORM` : ''}`);
      fetchAll(address);
    } else {
      setExecMsg('エラー: ' + (r.error || '不明'));
    }
  }

  function hasCredential(nodeId, service) {
    return credentials.some(c => c.node_id === nodeId && c.service === service);
  }

  async function saveCred() {
    if (!credForm) return;
    const dataObj = {};
    const template = CRED_TEMPLATES[credForm.service] || CRED_TEMPLATES.custom;
    for (const f of template) {
      dataObj[f.key] = credValues[f.key] || '';
    }
    const res = await fetch('/api/my/credentials', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        node_id: credForm.nodeId,
        service: credForm.service,
        credential_type: credForm.service,
        label: credForm.service,
        data: JSON.stringify(dataObj)
      })
    });
    const r = await res.json();
    if (r.success) {
      setCredForm(null);
      setCredValues({});
      fetchAll(address);
    }
  }

  async function deleteCred(id) {
    await fetch('/api/my/credentials', {
      method: 'DELETE',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ id })
    });
    fetchAll(address);
  }

  const [sending, setSending] = useState(false);
  async function sendMessage() {
    if (!chatInput.trim() || !chatNode || sending) return;
    setSending(true);
    const msg = chatInput.trim();
    setChatInput('');
    await fetch('/api/my/messages', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ address, node_id: chatNode, message: msg })
    });
    await fetchAll(address);
    setSending(false);
  }

  function saveProfileName() {
    const trimmed = nameInput.trim();
    if (trimmed) {
      localStorage.setItem('user_display_name', trimmed);
      setDisplayName(trimmed);
    }
    setEditingName(false);
    setNameInput('');
  }

  function saveWallet() {
    const addr = walletInput.trim().toLowerCase();
    if (addr && addr.startsWith('0x') && addr.length === 42) {
      localStorage.setItem('wallet_address', addr);
      setAddress(addr);
      setEditingWallet(false);
      setWalletInput('');
      setWalletError('');
      fetchAll(addr);
    } else {
      setWalletError('無効なアドレスです（0x...で始まる42文字）');
    }
  }

  function copyAddress() {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) return (
    <div style={{
      textAlign:'center', padding:80,
      color:'var(--text-muted)',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: '50%',
        border: '3px solid rgba(255,255,255,0.1)',
        borderTopColor: '#667eea',
        animation: 'spin 0.8s linear infinite',
        margin: '0 auto 16px',
      }} />
      読み込み中...
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );

  const totalScore = Math.round(data.nodes.reduce((s,n) => s + (n.total_score || 0), 0));
  const totalMORM = data.nodes.reduce((s,n) => s + (Number(n.morm_balance) || 0), 0).toFixed(2);
  const totalPending = data.nodes.reduce((s,n) => s + (Number(n.morm_pending) || 0), 0).toFixed(2);

  const glassCard = {
    background: 'rgba(255,255,255,0.04)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 16,
    padding: '1.25rem',
    boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
    transition: 'border-color 0.3s, transform 0.2s',
  };

  const gradientBtn = {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: '#fff', border: 'none', borderRadius: 10,
    padding: '8px 18px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
    boxShadow: '0 4px 15px rgba(102,126,234,0.3)',
    transition: 'all 0.25s',
  };

  const ghostBtn = {
    background: 'rgba(255,255,255,0.04)',
    color: 'var(--text-muted)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10, padding: '8px 16px',
    cursor: 'pointer', fontSize: 13, transition: 'all 0.2s',
  };

  return (
    <div>
      {/* ===== Profile Card ===== */}
      <div style={{
        ...glassCard,
        marginBottom: 24,
        position: 'relative',
        overflow: 'hidden',
        padding: '24px 28px',
      }}>
        {/* Gradient accent */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: 'linear-gradient(90deg, #667eea, #764ba2, #00d2ff)',
        }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              {/* Avatar */}
              <img src="/icons/avatar-default.svg" width={44} height={44} alt="Avatar" style={{
                borderRadius: '50%',
                boxShadow: '0 0 20px rgba(102,126,234,0.3)',
              }} />
              <div>
                {editingName ? (
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input
                      value={nameInput}
                      onChange={(e) => setNameInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') saveProfileName(); }}
                      placeholder="表示名を入力..."
                      style={{ padding: '4px 10px', fontSize: 14, width: 160 }}
                      autoFocus
                    />
                    <button onClick={saveProfileName} style={{ ...gradientBtn, padding: '4px 12px', fontSize: 12 }}>保存</button>
                    <button onClick={() => setEditingName(false)} style={{ ...ghostBtn, padding: '4px 10px', fontSize: 12 }}>取消</button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>
                      {displayName || '名前未設定'}
                    </span>
                    <button onClick={() => { setEditingName(true); setNameInput(displayName); }} style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--accent)', fontSize: 11, padding: '2px 6px',
                    }}>編集</button>
                  </div>
                )}
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>ノードオペレーター</div>
              </div>
            </div>

            {/* Wallet address row */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'rgba(255,255,255,0.03)', borderRadius: 8,
              padding: '8px 12px', border: '1px solid rgba(255,255,255,0.05)',
            }}>
              {editingWallet ? (
                <>
                  <input
                    value={walletInput}
                    onChange={(e) => setWalletInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') saveWallet(); }}
                    placeholder="0x..."
                    style={{ flex: 1, fontFamily: 'monospace', fontSize: 12, padding: '4px 8px' }}
                    autoFocus
                  />
                  <button onClick={saveWallet} style={{ ...gradientBtn, padding: '4px 12px', fontSize: 11 }}>保存</button>
                  <button onClick={() => { setEditingWallet(false); setWalletError(''); }} style={{ ...ghostBtn, padding: '4px 10px', fontSize: 11 }}>取消</button>
                </>
              ) : (
                <>
                  <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)', flex: 1, wordBreak: 'break-all' }}>
                    {address}
                  </span>
                  <button onClick={copyAddress} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: copied ? 'var(--green)' : 'var(--text-muted)',
                    fontSize: 11, padding: '2px 6px', transition: 'color 0.2s',
                  }}>{copied ? 'Copied!' : 'Copy'}</button>
                  <button onClick={() => { setEditingWallet(true); setWalletInput(address); }} style={{
                    background: 'none', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 6, padding: '3px 8px', cursor: 'pointer',
                    color: 'var(--accent)', fontSize: 11,
                  }}>ウォレット変更</button>
                </>
              )}
            </div>
            {walletError && <p style={{ marginTop: 6, fontSize: 12, color: 'var(--red)' }}>{walletError}</p>}
          </div>
        </div>
      </div>

      {/* ===== Header ===== */}
      <h1 style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #00d2ff 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
        fontSize: '1.6rem',
        marginBottom: 4,
      }}>マイページ</h1>

      {/* ===== Stats ===== */}
      <div className="grid-4" style={{marginBottom:24}}>
        <div className="stat-card">
          <div className="stat-value" style={{
            background: 'linear-gradient(135deg, #34d399, #059669)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>{data.nodes.filter(n=>n.status==='online').length}</div>
          <div className="stat-label">オンライン</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.nodes.length}</div>
          <div className="stat-label">マイノード</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>{totalScore}</div>
          <div className="stat-label">合計スコア</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{
            background: 'linear-gradient(135deg, #fbbf24, #f59e0b)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>{totalMORM}</div>
          <div className="stat-label">MORM残高</div>
        </div>
      </div>

      {/* ===== Tabs ===== */}
      <div style={{display:'flex',gap:6,marginBottom:24}}>
        {[['nodes','マイノード'],['tasks','タスク'],['scores','スコア'],['support','サポート']].map(([key,label])=>{
          const tabIcon = key === 'support' ? '/icons/chat-icon.svg' : null;
          return (
          <button key={key} onClick={()=>setTab(key)}
            style={{
              background: tab===key
                ? 'linear-gradient(135deg, #667eea, #764ba2)'
                : 'rgba(255,255,255,0.04)',
              border: tab===key ? 'none' : '1px solid rgba(255,255,255,0.08)',
              borderRadius:10,
              padding:'9px 22px',
              fontSize:14,
              fontWeight: tab===key ? 600 : 400,
              cursor:'pointer',
              color: tab===key ? '#fff' : 'var(--text-muted)',
              position:'relative',
              transition: 'all 0.25s',
              boxShadow: tab===key ? '0 4px 15px rgba(102,126,234,0.3)' : 'none',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
            {tabIcon && <img src={tabIcon} width={16} height={16} alt="" />}
            {label}
            {key==='support' && unreadAdmin > 0 && (
              <span style={{position:'absolute',top:-6,right:-6,background:'linear-gradient(135deg, #f87171, #dc2626)',color:'#fff',borderRadius:'50%',width:18,height:18,fontSize:10,display:'flex',alignItems:'center',justifyContent:'center',fontWeight:700,boxShadow:'0 2px 8px rgba(248,113,113,0.4)'}}>
                {unreadAdmin}
              </span>
            )}
          </button>
        );
        })}
      </div>

      {/* ===== Nodes Tab ===== */}
      {tab === 'nodes' && (
        <>
          <div style={{ ...glassCard, marginBottom:16 }}>
            <h2>PCを紐づける</h2>
            <p style={{color:'var(--text-muted)',fontSize:13,marginBottom:12}}>運営者から通知されたノードIDを入力してください。</p>
            <div style={{display:'flex',gap:8}}>
              <input value={linkId} onChange={e=>setLinkId(e.target.value)} placeholder="ノードID (例: claude_pc1)" style={{flex:1}} />
              <button onClick={linkNode} style={gradientBtn}>紐づける</button>
            </div>
            {linkMsg && <p style={{marginTop:8,fontSize:14,color:linkMsg.includes('エラー')?'var(--red)':'var(--green)'}}>{linkMsg}</p>}
          </div>

          {data.nodes.length > 0 ? (
            <div className="grid-2">
              {data.nodes.map(n=>(
                <div key={n.id} style={{ ...glassCard }}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                    <div style={{display:'flex',alignItems:'center',gap:8}}>
                      <img src={/mac|mini/i.test(n.name) ? '/icons/macmini-icon.svg' : '/icons/pc-icon.svg'} width={24} height={24} alt="" />
                      <strong style={{fontSize:16,color:'var(--text)'}}>{n.name}</strong>
                    </div>
                    <img src={n.status==='online' ? '/icons/node-online.svg' : '/icons/node-offline.svg'} width={22} height={22} alt={n.status} title={n.status==='online'?'オンライン':'オフライン'} />
                  </div>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,fontSize:13,color:'var(--text-muted)'}}>
                    <div>CPU: <strong style={{color:'var(--text)'}}>{n.cpu_cores}コア</strong></div>
                    <div>RAM: <strong style={{color:'var(--text)'}}>{n.ram_gb}GB</strong></div>
                    <div>容量: <strong style={{color:'var(--text)'}}>{n.storage_gb}GB</strong></div>
                    <div>使用: <strong style={{color:'var(--text)'}}>{n.storage_used_gb}GB</strong></div>
                  </div>
                  {n.connection_methods && (
                    <div style={{display:'flex',gap:6,marginTop:10,flexWrap:'wrap',alignItems:'center'}}>
                      {String(n.connection_methods).split(',').filter(Boolean).map(m => {
                        const connMap = {SSH:'conn-ssh',Tailscale:'conn-tailscale',WireGuard:'conn-wireguard',LAN:'conn-local',Local:'conn-local'};
                        const icon = connMap[m];
                        return (
                          <span key={m} className={`badge ${m==='SSH'||m==='Local'?'green':m==='Tailscale'?'blue':'yellow'}`} style={{fontSize:10,display:'inline-flex',alignItems:'center',gap:4}}>
                            {icon && <img src={`/icons/${icon}.svg`} width={14} height={14} alt="" />}
                            {m}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  <div style={{display:'flex',gap:4,marginTop:8,flexWrap:'wrap',alignItems:'center'}}>
                    {SERVICES.map(s => {
                      const conn = data.connections.find(c => c.node_id===n.id && c.service===s);
                      const ok = conn && conn.status==='connected';
                      const svcIconMap = {x:'svc-x',instagram:'svc-instagram',tiktok:'svc-tiktok',facebook:'svc-facebook',youtube:'svc-youtube',gmail:'svc-gmail',git:'svc-github',cloudflare:'svc-cloudflare'};
                      return (
                        <span key={s} className={`badge ${ok?'green':'red'}`} style={{fontSize:9,display:'inline-flex',alignItems:'center',gap:3}}>
                          <img src={`/icons/${svcIconMap[s]}.svg`} width={14} height={14} alt="" style={{opacity: ok ? 1 : 0.5}} />
                          {SVC_NAMES[s]}
                        </span>
                      );
                    })}
                  </div>
                  <div style={{marginTop:12,paddingTop:12,borderTop:'1px solid rgba(255,255,255,0.06)',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <div style={{fontSize:12,color:'var(--text-muted)'}}>基本 {n.base_score} + タスク {n.task_score}</div>
                    <div style={{
                      fontSize:24,fontWeight:700,
                      background:'linear-gradient(135deg, #667eea, #764ba2)',
                      WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                    }}>{Math.round(n.total_score)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ ...glassCard, textAlign:'center',padding:40,color:'var(--text-muted)' }}>
              <img src="/icons/empty-state.svg" width={80} height={80} alt="" style={{marginBottom:16,opacity:0.6}} />
              <div>まだノードが紐づけられていません。上のフォームからノードIDを入力してください。</div>
            </div>
          )}
        </>
      )}

      {/* ===== Tasks Tab ===== */}
      {tab === 'tasks' && (
        <>
          {/* MORM Balance */}
          <div style={{
            ...glassCard, marginBottom:16,
            background:'linear-gradient(135deg, rgba(102,126,234,0.08) 0%, rgba(118,75,162,0.08) 100%)',
            border: '1px solid rgba(102,126,234,0.15)',
          }}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <div>
                <div style={{fontSize:13,color:'var(--text-muted)',marginBottom:4}}>MORM残高</div>
                <div style={{
                  fontSize:30,fontWeight:700,
                  background:'linear-gradient(135deg, #fbbf24, #f59e0b)',
                  WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                  display:'flex',alignItems:'center',gap:8,
                }}><img src="/icons/morm-token-sm.svg" width={28} height={28} alt="" />{totalMORM} MORM</div>
              </div>
              <div style={{textAlign:'right',fontSize:12,color:'var(--text-muted)'}}>
                <div>獲得: {totalPending} MORM</div>
                <div>消費: {data.nodes.reduce((s,n) => s + (Number(n.morm_spent) || 0), 0).toFixed(2)} MORM</div>
              </div>
            </div>
          </div>

          {execMsg && (
            <div style={{
              ...glassCard, marginBottom:16, padding:'12px 16px',
              background: execMsg.includes('エラー') ? 'rgba(248,113,113,0.08)' : 'rgba(52,211,153,0.08)',
              border: `1px solid ${execMsg.includes('エラー') ? 'rgba(248,113,113,0.25)' : 'rgba(52,211,153,0.25)'}`,
            }}>
              <span style={{color:execMsg.includes('エラー')?'var(--red)':'var(--green)',fontSize:14}}>{execMsg}</span>
            </div>
          )}

          {/* Credential form modal */}
          {credForm && (
            <div style={{
              ...glassCard, marginBottom:16,
              border:'1px solid rgba(102,126,234,0.3)',
              boxShadow: '0 0 30px rgba(102,126,234,0.1)',
            }}>
              <h3 style={{marginBottom:12}}>{credForm.service} アカウント登録 ({credForm.nodeName})</h3>
              {(CRED_TEMPLATES[credForm.service] || CRED_TEMPLATES.custom).map(f => (
                <div key={f.key} style={{marginBottom:8}}>
                  <label style={{fontSize:12,color:'var(--text-muted)',display:'block',marginBottom:4}}>{f.label}</label>
                  <input
                    type={f.key.includes('password') || f.key.includes('secret') || f.key.includes('token') ? 'password' : 'text'}
                    value={credValues[f.key] || ''}
                    onChange={e => setCredValues({...credValues, [f.key]: e.target.value})}
                    style={{width:'100%'}}
                  />
                </div>
              ))}
              <div style={{display:'flex',gap:8,marginTop:12}}>
                <button onClick={saveCred} style={gradientBtn}>保存</button>
                <button onClick={()=>{setCredForm(null);setCredValues({})}} style={ghostBtn}>キャンセル</button>
              </div>
            </div>
          )}

          {/* Tasks per node */}
          {data.nodes.map(n => (
            <div key={n.id} style={{ ...glassCard, marginBottom:16 }}>
              <h2 style={{marginBottom:12}}>{n.name} のタスク</h2>
              <table>
                <thead>
                  <tr><th>タスク名</th><th>カテゴリ</th><th>スコア</th><th>MORM</th><th>認証</th><th>操作</th></tr>
                </thead>
                <tbody>
                  {taskData.tasks.map(t => {
                    const needsCred = !!t.requires_credential;
                    const hasCred = needsCred ? hasCredential(n.id, t.requires_credential) : true;
                    const mormCost = Number(t.morm_cost) || 0;
                    const balance = Number(n.morm_balance) || 0;
                    const canAfford = mormCost <= 0 || balance >= mormCost;
                    const canExec = hasCred && canAfford;

                    return (
                      <tr key={t.id}>
                        <td style={{color:'var(--text)'}}>{t.name}</td>
                        <td><span className="badge blue" style={{fontSize:11,display:'inline-flex',alignItems:'center',gap:4}}><img src={`/icons/task-${t.category}.svg`} width={16} height={16} alt="" />{CAT_NAMES[t.category]||t.category}</span></td>
                        <td style={{color:'var(--green)',fontWeight:700}}>+{t.score_value}</td>
                        <td>{mormCost > 0 ? <span style={{color:'var(--yellow)',fontWeight:600,display:'inline-flex',alignItems:'center',gap:4}}><img src="/icons/morm-token-sm.svg" width={14} height={14} alt="" />-{mormCost} MORM</span> : <span style={{color:'var(--text-muted)'}}>-</span>}</td>
                        <td>
                          {needsCred ? (
                            hasCred ? (
                              <span style={{color:'var(--green)',fontSize:13}}>OK</span>
                            ) : (
                              <button onClick={()=>{setCredForm({nodeId:n.id,nodeName:n.name,service:t.requires_credential});setCredValues({})}} style={{background:'none',border:'1px solid rgba(248,113,113,0.3)',borderRadius:6,padding:'2px 8px',fontSize:11,color:'var(--red)',cursor:'pointer'}}>
                                要登録
                              </button>
                            )
                          ) : <span style={{color:'var(--text-muted)'}}>-</span>}
                        </td>
                        <td>
                          <button
                            onClick={()=>executeTask(n.id, t.id)}
                            disabled={!canExec}
                            style={{
                              background: canExec ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.04)',
                              color: canExec ? '#fff' : 'var(--text-muted)',
                              border:'none', borderRadius:8, padding:'5px 14px', fontSize:12,
                              cursor: canExec ? 'pointer' : 'not-allowed',
                              boxShadow: canExec ? '0 2px 10px rgba(102,126,234,0.25)' : 'none',
                              transition: 'all 0.2s',
                            }}
                          >
                            実行
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}

          {/* Registered credentials */}
          {credentials.length > 0 && (
            <div style={{ ...glassCard, marginBottom:16 }}>
              <h2 style={{marginBottom:12}}>登録済みアカウント</h2>
              <table>
                <thead><tr><th>ノード</th><th>サービス</th><th>データ</th><th>操作</th></tr></thead>
                <tbody>
                  {credentials.map(c => (
                    <tr key={c.id}>
                      <td style={{fontSize:12,color:'var(--text-secondary)'}}>{c.node_id}</td>
                      <td><span className="badge blue" style={{fontSize:11}}>{c.service}</span></td>
                      <td style={{fontSize:11,fontFamily:'monospace',color:'var(--text-muted)'}}>{c.data}</td>
                      <td>
                        <button onClick={()=>deleteCred(c.id)} style={{background:'none',border:'1px solid rgba(248,113,113,0.3)',borderRadius:6,padding:'2px 8px',fontSize:11,color:'var(--red)',cursor:'pointer'}}>削除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Task execution history */}
          <div style={glassCard}>
            <h2>タスク実行履歴</h2>
            {taskData.runs.length > 0 ? (
              <table>
                <thead><tr><th>タスク</th><th>カテゴリ</th><th>ノード</th><th>ステータス</th><th>スコア</th></tr></thead>
                <tbody>
                  {taskData.runs.map(r=>(
                    <tr key={r.id}>
                      <td><strong style={{color:'var(--text)'}}>{r.task_name}</strong></td>
                      <td><span className="badge blue" style={{fontSize:11}}>{CAT_NAMES[r.category]||r.category}</span></td>
                      <td style={{fontSize:12,color:'var(--text-secondary)'}}>{r.node_name}</td>
                      <td><span className={`badge ${r.status==='success'?'green':r.status==='failed'?'red':'yellow'}`}>{r.status==='success'?'成功':r.status==='failed'?'失敗':'実行中'}</span></td>
                      <td style={{color:'var(--green)',fontWeight:700}}>+{r.score_earned}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{textAlign:'center',padding:24}}>
              <img src="/icons/empty-state.svg" width={60} height={60} alt="" style={{marginBottom:12,opacity:0.5}} />
              <p style={{color:'var(--text-muted)'}}>まだタスク履歴がありません</p>
            </div>
            )}
          </div>
        </>
      )}

      {/* ===== Scores Tab ===== */}
      {tab === 'scores' && (
        <div style={glassCard}>
          <h2 style={{display:'flex',alignItems:'center',gap:8}}><img src="/icons/score-trophy.svg" width={24} height={24} alt="" />スコア内訳</h2>
          {data.nodes.length > 0 ? (
            <>
              {data.nodes.map(n=>(
                <div key={n.id} style={{marginBottom:24}}>
                  <h3 style={{marginBottom:12}}>{n.name}</h3>
                  <div className="grid-3">
                    <div className="stat-card">
                      <div className="stat-value" style={{fontSize:28}}>{n.base_score}</div>
                      <div className="stat-label">基本スコア</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value" style={{
                        fontSize:28,
                        background:'linear-gradient(135deg, #34d399, #059669)',
                        WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                      }}>{n.task_score}</div>
                      <div className="stat-label">タスクスコア</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value" style={{
                        fontSize:28,
                        background:'linear-gradient(135deg, #667eea, #764ba2)',
                        WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                      }}>{Math.round(n.total_score)}</div>
                      <div className="stat-label">合計</div>
                    </div>
                  </div>
                  {/* MORM breakdown */}
                  <div className="grid-3" style={{marginTop:8}}>
                    <div className="stat-card">
                      <div className="stat-value" style={{
                        fontSize:22,
                        background:'linear-gradient(135deg, #fbbf24, #f59e0b)',
                        WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                      }}>{(Number(n.morm_pending)||0).toFixed(2)}</div>
                      <div className="stat-label">獲得MORM</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value" style={{
                        fontSize:22,
                        background:'linear-gradient(135deg, #f87171, #dc2626)',
                        WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                      }}>{(Number(n.morm_spent)||0).toFixed(2)}</div>
                      <div className="stat-label">消費MORM</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-value" style={{
                        fontSize:22,
                        background:'linear-gradient(135deg, #667eea, #00d2ff)',
                        WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',
                      }}>{(Number(n.morm_balance)||0).toFixed(2)}</div>
                      <div className="stat-label">MORM残高</div>
                    </div>
                  </div>
                </div>
              ))}
            </>
          ) : (
            <p style={{color:'var(--text-muted)',textAlign:'center',padding:32}}>ノードを紐づけるとスコアが表示されます</p>
          )}
        </div>
      )}

      {/* ===== Support / Chat Tab ===== */}
      {tab === 'support' && (
        <div style={{
          ...glassCard,
          display:'flex',flexDirection:'column',minHeight:400,
        }}>
          <h2 style={{marginBottom:12}}>サポートチャット</h2>

          {data.nodes.length > 1 && (
            <div style={{marginBottom:12}}>
              <select value={chatNode} onChange={e=>setChatNode(e.target.value)} style={{
                padding:'8px 14px',borderRadius:10,
                border:'1px solid rgba(255,255,255,0.1)',
                background:'rgba(255,255,255,0.04)',
                color:'var(--text)',
              }}>
                {data.nodes.map(n=>(
                  <option key={n.id} value={n.id}>{n.name}</option>
                ))}
              </select>
            </div>
          )}

          <div style={{
            flex:1, overflowY:'auto', maxHeight:400, padding:14,
            background:'rgba(255,255,255,0.02)', borderRadius:12, marginBottom:12,
            border:'1px solid rgba(255,255,255,0.04)',
          }}>
            {messages.filter(m => m.node_id === chatNode).length === 0 ? (
              <p style={{textAlign:'center',color:'var(--text-muted)',padding:40}}>メッセージはありません</p>
            ) : (
              messages.filter(m => m.node_id === chatNode).map(m => (
                <div key={m.id} style={{
                  display:'flex',
                  justifyContent: m.sender === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom:8
                }}>
                  <div style={{
                    maxWidth:'70%',
                    padding:'10px 16px',
                    borderRadius:14,
                    background: m.sender === 'user'
                      ? 'linear-gradient(135deg, #667eea, #764ba2)'
                      : 'rgba(255,255,255,0.06)',
                    color: '#fff',
                    fontSize:14,
                    boxShadow: m.sender === 'user'
                      ? '0 2px 12px rgba(102,126,234,0.25)'
                      : '0 2px 8px rgba(0,0,0,0.2)',
                  }}>
                    <div style={{ color: m.sender === 'user' ? '#fff' : 'var(--text)' }}>{m.message}</div>
                    <div style={{fontSize:10,color: m.sender==='user' ? 'rgba(255,255,255,0.5)' : 'var(--text-muted)',marginTop:4,textAlign:'right'}}>
                      {m.created_at ? new Date(m.created_at).toLocaleString('ja-JP') : ''}
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          <div style={{display:'flex',gap:8}}>
            <input
              value={chatInput}
              onChange={e=>setChatInput(e.target.value)}
              onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();sendMessage()}}}
              placeholder="メッセージを入力..."
              style={{flex:1}}
            />
            <button onClick={sendMessage} disabled={sending || !chatInput.trim()} style={{...gradientBtn, opacity: sending?0.5:1}}>
              {sending ? '...' : '送信'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

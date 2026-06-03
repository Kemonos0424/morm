'use client';

import { useState, useEffect, useRef } from 'react';
import HelpButton from '@/app/components/HelpButton';

export default function AdminChatPage() {
  const [nodes, setNodes] = useState([]);
  const [allNodes, setAllNodes] = useState([]);
  const [messages, setMessages] = useState([]);
  const [unreadMap, setUnreadMap] = useState({});
  const [selectedNode, setSelectedNode] = useState('');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchMessages();
    const interval = setInterval(fetchMessages, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (chatEndRef.current) chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, selectedNode]);

  async function fetchMessages() {
    try {
      const [msgRes, nodeRes] = await Promise.all([
        fetch('/api/admin/messages'),
        fetch('/api/nodes')
      ]);
      const data = await msgRes.json();
      const nodeData = await nodeRes.json();
      setNodes(data.nodes || []);
      setAllNodes(nodeData || []);
      setMessages(data.messages || []);
      setUnreadMap(data.unreadMap || {});
      if (!selectedNode && data.nodes && data.nodes.length > 0) {
        setSelectedNode(data.nodes[0].id);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function sendReply() {
    if (!input.trim() || !selectedNode || sending) return;
    setSending(true);
    await fetch('/api/admin/messages', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ node_id: selectedNode, message: input.trim() })
    });
    setInput('');
    await fetchMessages();
    setSending(false);
  }

  const totalUnread = Object.values(unreadMap).reduce((s, v) => s + v, 0);
  const filteredMessages = messages.filter(m => m.node_id === selectedNode);
  const selectedNodeInfo = allNodes.find(n => n.id === selectedNode);

  function getTimeSince(dateStr) {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr + 'Z').getTime();
    const min = Math.floor(diff / 60000);
    if (min < 1) return 'たった今';
    if (min < 60) return `${min}分前`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}時間前`;
    const day = Math.floor(hr / 24);
    return `${day}日前`;
  }

  function getLastMessage(nodeId) {
    const nodeMessages = messages.filter(m => m.node_id === nodeId);
    if (nodeMessages.length === 0) return null;
    return nodeMessages[nodeMessages.length - 1];
  }

  if (loading) return <div style={{textAlign:'center',padding:80,color:'var(--text-muted)'}}>読み込み中...</div>;

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:24}}>
        <h1 style={{margin:0,display:'flex',alignItems:'center',gap:8}}><img src="/icons/chat-icon.svg" width={28} height={28} alt="" />チャット管理 <HelpButton title="チャットサポートについて"><p>ノード提供者からのメッセージを管理するページです。</p><p>左のリストからノードを選択するとチャット履歴が表示されます。</p><p>未読メッセージがあるノードには赤いバッジが表示されます。</p><p>返信を入力して「送信」で返事ができます。</p><p>10秒ごとに自動更新されます。</p></HelpButton></h1>
        {totalUnread > 0 && (
          <span style={{
            background:'linear-gradient(135deg,#ef4444,#f97316)',color:'#fff',
            borderRadius:20,padding:'6px 16px',fontSize:14,fontWeight:700
          }}>
            {totalUnread}件の未読
          </span>
        )}
      </div>

      <div style={{display:'flex',gap:16}}>
        {/* Left: Node list */}
        <div style={{width:280,flexShrink:0}}>
          <div className="card" style={{padding:0,overflow:'hidden'}}>
            <div style={{padding:'14px 16px',borderBottom:'1px solid var(--border)',background:'rgba(102,126,234,0.05)'}}>
              <strong style={{fontSize:14}}>受信トレイ ({nodes.length})</strong>
            </div>

            {nodes.length === 0 ? (
              <div style={{padding:32,textAlign:'center',color:'var(--text-muted)',fontSize:13}}>
                まだメッセージがありません
              </div>
            ) : (
              <div style={{maxHeight:500,overflowY:'auto'}}>
                {nodes.map(n => {
                  const lastMsg = getLastMessage(n.id);
                  const unread = unreadMap[n.id] || 0;
                  const nodeInfo = allNodes.find(an => an.id === n.id);
                  return (
                    <div
                      key={n.id}
                      onClick={() => setSelectedNode(n.id)}
                      style={{
                        padding:'12px 16px',
                        cursor:'pointer',
                        background: selectedNode === n.id ? 'rgba(102,126,234,0.1)' : 'transparent',
                        borderLeft: selectedNode === n.id ? '3px solid #667eea' : '3px solid transparent',
                        borderBottom:'1px solid var(--border)',
                        transition:'background 0.15s'
                      }}
                    >
                      {/* Header: name + unread badge */}
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
                        <div style={{display:'flex',alignItems:'center',gap:8}}>
                          {/* Avatar */}
                          <img src="/icons/avatar-default.svg" width={32} height={32} alt="" style={{borderRadius:'50%',flexShrink:0,opacity: unread > 0 ? 1 : 0.6}} />
                          <div>
                            <div style={{fontSize:14,fontWeight:unread>0?700:500,color:'var(--text)'}}>{n.name}</div>
                            <div style={{fontSize:11,color:'var(--text-muted)'}}>
                              {nodeInfo?.status === 'online' ? '🟢' : '🔴'} {n.id}
                            </div>
                          </div>
                        </div>
                        {unread > 0 && (
                          <span style={{
                            background:'linear-gradient(135deg,#667eea,#764ba2)',color:'#fff',
                            borderRadius:12,minWidth:22,height:22,fontSize:11,fontWeight:700,
                            display:'flex',alignItems:'center',justifyContent:'center',padding:'0 6px'
                          }}>
                            {unread}
                          </span>
                        )}
                      </div>

                      {/* Last message preview */}
                      {lastMsg && (
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginLeft:40}}>
                          <div style={{
                            fontSize:12,color:'var(--text-muted)',
                            overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',
                            maxWidth:150,fontWeight:unread>0?600:400
                          }}>
                            {lastMsg.sender === 'admin' ? '↩ ' : ''}{lastMsg.message}
                          </div>
                          <div style={{fontSize:10,color:'var(--text-muted)',flexShrink:0,marginLeft:8}}>
                            {getTimeSince(lastMsg.created_at)}
                          </div>
                        </div>
                      )}

                      {/* Wallet address */}
                      {nodeInfo?.wallet_address && (
                        <div style={{fontSize:10,color:'var(--text-muted)',marginLeft:40,marginTop:2,fontFamily:'monospace'}}>
                          {nodeInfo.wallet_address.slice(0,6)}...{nodeInfo.wallet_address.slice(-4)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right: Chat thread */}
        <div style={{flex:1}}>
          <div className="card" style={{display:'flex',flexDirection:'column',minHeight:520,padding:0,overflow:'hidden'}}>
            {/* Chat header with node info */}
            {selectedNode && selectedNodeInfo ? (
              <div style={{
                padding:'16px 20px',
                borderBottom:'1px solid var(--border)',
                background:'rgba(102,126,234,0.03)',
                display:'flex',justifyContent:'space-between',alignItems:'center'
              }}>
                <div style={{display:'flex',alignItems:'center',gap:12}}>
                  <div style={{
                    width:40,height:40,borderRadius:'50%',
                    background:'linear-gradient(135deg,#667eea,#764ba2)',
                    display:'flex',alignItems:'center',justifyContent:'center',
                    fontSize:18,fontWeight:700,color:'#fff'
                  }}>
                    {(nodes.find(n=>n.id===selectedNode)?.name || 'N').charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div style={{fontSize:16,fontWeight:700}}>{nodes.find(n=>n.id===selectedNode)?.name || selectedNode}</div>
                    <div style={{fontSize:12,color:'var(--text-muted)',display:'flex',gap:12,alignItems:'center'}}>
                      <span>{selectedNodeInfo.status === 'online' ? '🟢 オンライン' : '🔴 オフライン'}</span>
                      <span>CPU: {selectedNodeInfo.cpu_cores}コア</span>
                      <span>RAM: {selectedNodeInfo.ram_gb}GB</span>
                      {selectedNodeInfo.wallet_address && (
                        <span style={{fontFamily:'monospace'}}>{selectedNodeInfo.wallet_address.slice(0,6)}...{selectedNodeInfo.wallet_address.slice(-4)}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div style={{display:'flex',gap:8}}>
                  <span className={`badge ${selectedNodeInfo.status==='online'?'green':'red'}`}>{selectedNodeInfo.status}</span>
                  <span className="badge blue">スコア: {selectedNodeInfo.total_score}</span>
                </div>
              </div>
            ) : (
              <div style={{padding:'16px 20px',borderBottom:'1px solid var(--border)'}}>
                <strong>ノードを選択してください</strong>
              </div>
            )}

            {/* Messages */}
            <div style={{flex:1,overflowY:'auto',padding:20,background:'rgba(0,0,0,0.02)'}}>
              {filteredMessages.length === 0 ? (
                <p style={{textAlign:'center',color:'var(--text-muted)',padding:60,fontSize:14}}>メッセージはありません</p>
              ) : (
                <>
                  {filteredMessages.map((m, i) => {
                    const isAdmin = m.sender === 'admin';
                    // Show date separator
                    const prevMsg = i > 0 ? filteredMessages[i-1] : null;
                    const currentDate = m.created_at ? m.created_at.split(' ')[0] : '';
                    const prevDate = prevMsg?.created_at ? prevMsg.created_at.split(' ')[0] : '';
                    const showDate = currentDate !== prevDate;

                    return (
                      <div key={m.id}>
                        {showDate && (
                          <div style={{textAlign:'center',margin:'16px 0',fontSize:11,color:'var(--text-muted)'}}>
                            <span style={{background:'var(--card)',padding:'4px 12px',borderRadius:12,border:'1px solid var(--border)'}}>
                              {currentDate}
                            </span>
                          </div>
                        )}
                        <div style={{
                          display:'flex',
                          justifyContent: isAdmin ? 'flex-end' : 'flex-start',
                          marginBottom:12
                        }}>
                          {/* User avatar (left side) */}
                          {!isAdmin && (
                            <div style={{
                              width:28,height:28,borderRadius:'50%',
                              background:'linear-gradient(135deg,#667eea,#764ba2)',
                              display:'flex',alignItems:'center',justifyContent:'center',
                              fontSize:12,fontWeight:700,color:'#fff',marginRight:8,flexShrink:0,marginTop:4
                            }}>
                              {(m.node_name || 'U').charAt(0).toUpperCase()}
                            </div>
                          )}
                          <div style={{
                            maxWidth:'65%',
                            padding:'10px 16px',
                            borderRadius: isAdmin ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                            background: isAdmin
                              ? 'linear-gradient(135deg,#667eea,#764ba2)'
                              : 'var(--card)',
                            color: isAdmin ? '#fff' : 'var(--text)',
                            fontSize:14,
                            border: isAdmin ? 'none' : '1px solid var(--border)',
                            boxShadow:'0 1px 3px rgba(0,0,0,0.05)'
                          }}>
                            {/* Sender label */}
                            <div style={{
                              fontSize:11,fontWeight:600,marginBottom:4,
                              color: isAdmin ? 'rgba(255,255,255,0.7)' : '#667eea'
                            }}>
                              {isAdmin ? '運営' : `${m.node_name || m.node_id}`}
                            </div>
                            <div style={{lineHeight:1.5}}>{m.message}</div>
                            <div style={{
                              fontSize:10,marginTop:6,textAlign:'right',
                              color: isAdmin ? 'rgba(255,255,255,0.5)' : 'var(--text-muted)'
                            }}>
                              {m.created_at ? new Date(m.created_at + 'Z').toLocaleTimeString('ja-JP', {hour:'2-digit',minute:'2-digit'}) : ''}
                            </div>
                          </div>
                          {/* Admin avatar (right side) */}
                          {isAdmin && (
                            <div style={{
                              width:28,height:28,borderRadius:'50%',
                              background:'linear-gradient(135deg,#22c55e,#16a34a)',
                              display:'flex',alignItems:'center',justifyContent:'center',
                              fontSize:12,fontWeight:700,color:'#fff',marginLeft:8,flexShrink:0,marginTop:4
                            }}>
                              A
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  <div ref={chatEndRef} />
                </>
              )}
            </div>

            {/* Reply form */}
            {selectedNode && (
              <div style={{padding:16,borderTop:'1px solid var(--border)',display:'flex',gap:8}}>
                <input
                  value={input}
                  onChange={e=>setInput(e.target.value)}
                  onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();sendReply()}}}
                  placeholder="返信を入力..."
                  style={{flex:1}}
                  disabled={sending}
                />
                <button
                  onClick={sendReply}
                  disabled={sending || !input.trim()}
                  style={{
                    background:'linear-gradient(135deg,#667eea,#764ba2)',color:'#fff',
                    border:'none',borderRadius:8,padding:'10px 24px',cursor:'pointer',
                    fontWeight:600,fontSize:14,opacity:sending?0.5:1
                  }}
                >
                  {sending ? '...' : '送信'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

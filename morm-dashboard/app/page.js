'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function Home() {
  const [address, setAddress] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [editingAddress, setEditingAddress] = useState(false);
  const [addressInput, setAddressInput] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('wallet_address');
    if (saved) setAddress(saved);
    const savedName = localStorage.getItem('user_display_name');
    if (savedName) setDisplayName(savedName);
  }, []);

  async function connectWallet() {
    if (typeof window === 'undefined' || !window.ethereum) {
      setError('ウォレットが検出されません。MetaMask等をインストールしてください。');
      return;
    }
    setConnecting(true);
    setError('');
    try {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      const addr = accounts[0].toLowerCase();
      localStorage.setItem('wallet_address', addr);
      setAddress(addr);
    } catch (err) {
      setError(err.message || '接続に失敗しました');
    }
    setConnecting(false);
  }

  async function connectManual() {
    const addr = prompt('ウォレットアドレスを入力 (0x...)');
    if (addr && addr.startsWith('0x') && addr.length === 42) {
      localStorage.setItem('wallet_address', addr.toLowerCase());
      setAddress(addr.toLowerCase());
    } else if (addr) {
      setError('無効なアドレスです（0x...で始まる42文字）');
    }
  }

  function disconnect() {
    localStorage.removeItem('wallet_address');
    localStorage.removeItem('user_display_name');
    setAddress(null);
    setDisplayName('');
  }

  function saveDisplayName() {
    const trimmed = nameInput.trim();
    if (trimmed) {
      localStorage.setItem('user_display_name', trimmed);
      setDisplayName(trimmed);
    }
    setEditingName(false);
    setNameInput('');
  }

  function saveAddress() {
    const addr = addressInput.trim().toLowerCase();
    if (addr && addr.startsWith('0x') && addr.length === 42) {
      localStorage.setItem('wallet_address', addr);
      setAddress(addr);
      setEditingAddress(false);
      setAddressInput('');
    } else {
      setError('無効なアドレスです（0x...で始まる42文字）');
    }
  }

  function copyAddress() {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: '2rem',
      position: 'relative',
      backgroundImage: 'url(/icons/hero-bg.png)',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }}>
      {/* Dark overlay for hero-bg */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(10, 10, 26, 0.85)',
        pointerEvents: 'none',
        zIndex: 0,
      }} />
      {/* Animated background orbs */}
      <div style={{
        position: 'fixed', top: '10%', left: '15%',
        width: 300, height: 300,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(102,126,234,0.12) 0%, transparent 70%)',
        filter: 'blur(60px)',
        animation: 'float 8s ease-in-out infinite',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'fixed', bottom: '15%', right: '10%',
        width: 250, height: 250,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(118,75,162,0.1) 0%, transparent 70%)',
        filter: 'blur(60px)',
        animation: 'float 10s ease-in-out infinite reverse',
        pointerEvents: 'none',
      }} />

      {/* Brand */}
      <div style={{ marginBottom: '0.5rem', animation: 'fade-in 0.6s ease-out', position: 'relative', zIndex: 1 }}>
        <div style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          letterSpacing: '0.15em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          marginBottom: '0.5rem',
          textAlign: 'center',
        }}>
          PCクラスタ管理 & MORM（m0r）トークンリワード
        </div>
        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: 800,
          textAlign: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 30%, #00d2ff 100%)',
          backgroundSize: '200% 200%',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          animation: 'gradient-shift 6s ease infinite',
          letterSpacing: '-0.02em',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.5rem',
        }}>
          <img src="/icons/logo.svg" width={40} height={40} alt="Logo" style={{ display: 'inline-block' }} />
          Node Dashboard
        </h1>
      </div>

      {!address ? (
        <>
        {/* ===== Connect Card ===== */}
        <div style={{
          maxWidth: 440,
          width: '100%',
          padding: 36,
          background: 'rgba(255,255,255,0.04)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 20,
          boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
          animation: 'fade-in 0.5s ease-out',
          position: 'relative',
          overflow: 'hidden',
          zIndex: 1,
        }}>
          {/* Gradient accent line at top */}
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, height: 2,
            background: 'linear-gradient(90deg, #667eea, #764ba2, #00d2ff)',
          }} />

          <h2 style={{ marginBottom: 8, fontSize: '1.15rem', color: 'var(--text)', textAlign: 'center' }}>
            ウォレットを接続
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 28, textAlign: 'center' }}>
            ウォレットでサインインして、ノード状況とMORM報酬を確認
          </p>

          <button
            onClick={connectWallet}
            disabled={connecting}
            style={{
              width: '100%', padding: '14px 20px', marginBottom: 12,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              backgroundSize: '200% 200%',
              border: 'none', borderRadius: 12,
              fontSize: 15, cursor: 'pointer',
              color: '#fff', fontWeight: 700,
              transition: 'all 0.3s',
              boxShadow: '0 4px 20px rgba(102, 126, 234, 0.35)',
              animation: 'gradient-shift 4s ease infinite',
              letterSpacing: '0.02em',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.boxShadow = '0 6px 30px rgba(102, 126, 234, 0.55)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(102, 126, 234, 0.35)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <img src="/icons/wallet-icon.svg" width={18} height={18} alt="" />
              {connecting ? '接続中...' : 'ウォレットコネクト'}
            </span>
          </button>

          <button
            onClick={connectManual}
            style={{
              width: '100%', padding: '12px 20px',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12, fontSize: 14, cursor: 'pointer',
              color: 'var(--text-secondary)', fontWeight: 500,
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
            }}
          >
            アドレスを直接入力
          </button>

          {error && <p style={{ marginTop: 14, fontSize: 14, color: 'var(--red)', textAlign: 'center' }}>{error}</p>}
        </div>
        {/* Network illustration below card */}
        <img src="/icons/network-illustration.svg" width={200} alt="" style={{ marginTop: 24, opacity: 0.5, position: 'relative', zIndex: 1 }} />
        </>
      ) : (
        /* ===== Connected / Profile Card ===== */
        <div style={{
          maxWidth: 480,
          width: '100%',
          animation: 'fade-in 0.5s ease-out',
          position: 'relative',
          zIndex: 1,
        }}>
          {/* Connected status card */}
          <div style={{
            padding: 32,
            background: 'rgba(255,255,255,0.04)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 20,
            boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
            position: 'relative',
            overflow: 'hidden',
            marginBottom: 16,
          }}>
            {/* Gradient accent line at top */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 2,
              background: 'linear-gradient(90deg, #34d399, #667eea, #764ba2)',
            }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <span style={{
                display: 'inline-block', padding: '0.25rem 0.75rem',
                borderRadius: 9999, fontSize: 12, fontWeight: 600,
                background: 'rgba(52, 211, 153, 0.12)', color: '#34d399',
                border: '1px solid rgba(52, 211, 153, 0.2)',
              }}>
                接続済み
              </span>
              {displayName && (
                <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>
                  {displayName}
                </span>
              )}
            </div>

            {/* Wallet Address */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'rgba(255,255,255,0.03)',
              borderRadius: 10, padding: '10px 14px',
              border: '1px solid rgba(255,255,255,0.06)',
              marginBottom: 20,
            }}>
              <p style={{
                fontFamily: 'monospace', fontSize: '0.8rem', wordBreak: 'break-all',
                color: 'var(--text-muted)', lineHeight: 1.5, flex: 1, margin: 0,
              }}>
                {address}
              </p>
              <button
                onClick={copyAddress}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: copied ? 'var(--green)' : 'var(--text-muted)',
                  fontSize: 12, padding: '4px 8px', borderRadius: 6,
                  transition: 'color 0.2s', whiteSpace: 'nowrap',
                }}
              >
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>

            {/* Action buttons */}
            <Link href="/my">
              <button style={{
                width: '100%', marginBottom: 10, padding: '13px 24px', fontSize: 15,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                borderRadius: 12, color: '#fff', border: 'none',
                fontWeight: 700, cursor: 'pointer', transition: 'all 0.3s',
                boxShadow: '0 4px 20px rgba(102, 126, 234, 0.35)',
                letterSpacing: '0.02em',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.boxShadow = '0 6px 30px rgba(102, 126, 234, 0.55)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.boxShadow = '0 4px 20px rgba(102, 126, 234, 0.35)';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
              >
                マイページへ
              </button>
            </Link>
            <button onClick={disconnect}
              style={{
                width: '100%', background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'var(--text-secondary)', borderRadius: 12, padding: '11px',
                cursor: 'pointer', fontSize: 14, fontWeight: 500,
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                e.currentTarget.style.borderColor = 'rgba(248,113,113,0.3)';
                e.currentTarget.style.color = '#f87171';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }}
            >
              接続を解除
            </button>
          </div>

          {/* Profile Editing Card */}
          <div style={{
            padding: 24,
            background: 'rgba(255,255,255,0.03)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 16,
            boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
          }}>
            <h3 style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
              プロフィール設定
            </h3>

            {/* Display Name */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                表示名
              </label>
              {editingName ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') saveDisplayName(); }}
                    placeholder="表示名を入力..."
                    style={{ flex: 1 }}
                    autoFocus
                  />
                  <button onClick={saveDisplayName} style={{
                    background: 'linear-gradient(135deg, #667eea, #764ba2)',
                    color: '#fff', border: 'none', borderRadius: 8,
                    padding: '6px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  }}>保存</button>
                  <button onClick={() => setEditingName(false)} style={{
                    background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
                    padding: '6px 12px', cursor: 'pointer', fontSize: 13,
                  }}>取消</button>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: displayName ? 'var(--text)' : 'var(--text-muted)', fontSize: 14 }}>
                    {displayName || '未設定'}
                  </span>
                  <button onClick={() => { setEditingName(true); setNameInput(displayName); }} style={{
                    background: 'none', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 6, padding: '3px 10px', cursor: 'pointer',
                    color: 'var(--accent)', fontSize: 12,
                  }}>編集</button>
                </div>
              )}
            </div>

            {/* Wallet Address Change */}
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                ウォレットアドレス
              </label>
              {editingAddress ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    value={addressInput}
                    onChange={(e) => setAddressInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') saveAddress(); }}
                    placeholder="0x..."
                    style={{ flex: 1, fontFamily: 'monospace', fontSize: 13 }}
                    autoFocus
                  />
                  <button onClick={saveAddress} style={{
                    background: 'linear-gradient(135deg, #667eea, #764ba2)',
                    color: '#fff', border: 'none', borderRadius: 8,
                    padding: '6px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
                  }}>保存</button>
                  <button onClick={() => { setEditingAddress(false); setAddressInput(''); setError(''); }} style={{
                    background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)',
                    border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
                    padding: '6px 12px', cursor: 'pointer', fontSize: 13,
                  }}>取消</button>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)' }}>
                    {address.slice(0, 8)}...{address.slice(-6)}
                  </span>
                  <button onClick={() => { setEditingAddress(true); setAddressInput(address); }} style={{
                    background: 'none', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 6, padding: '3px 10px', cursor: 'pointer',
                    color: 'var(--accent)', fontSize: 12,
                  }}>ウォレット変更</button>
                </div>
              )}
              {error && editingAddress && <p style={{ marginTop: 8, fontSize: 13, color: 'var(--red)' }}>{error}</p>}
            </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: '2rem', animation: 'fade-in 0.8s ease-out', position: 'relative', zIndex: 1 }}>
        <Link href="/admin" style={{ color: 'var(--text-muted)', fontSize: 13, transition: 'color 0.2s' }}>管理者ログイン →</Link>
      </div>
    </div>
  );
}

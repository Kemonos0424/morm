'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function MyLayout({ children }) {
  const router = useRouter();

  function logout() {
    localStorage.removeItem('wallet_address');
    router.push('/');
  }

  return (
    <div>
      <nav className="nav" style={{
        background: 'rgba(12, 12, 29, 0.85)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <span className="brand" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          <span style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #00d2ff 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            fontWeight: 800,
            fontSize: '1.05rem',
            letterSpacing: '-0.01em',
          }}>
            Node Dashboard
          </span>
        </span>
        <Link href="/my">マイページ</Link>
        <Link href="/my/rewards">MORM Claim</Link>
        <button
          className="btn-sm"
          onClick={logout}
          style={{
            marginLeft: 'auto',
            background: 'rgba(255,255,255,0.04)',
            color: 'var(--text-secondary)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.2s',
            padding: '6px 14px',
            fontSize: '0.8rem',
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.borderColor = 'rgba(248,113,113,0.3)';
            e.currentTarget.style.color = '#f87171';
            e.currentTarget.style.background = 'rgba(248,113,113,0.08)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)';
            e.currentTarget.style.color = 'var(--text-secondary)';
            e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
          }}
        >
          ログアウト
        </button>
      </nav>
      <div className="container">{children}</div>
    </div>
  );
}

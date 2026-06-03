'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/admin/dashboard', label: 'ホーム' },
  { href: '/admin/nodes', label: 'ノード' },
  { href: '/admin/tasks', label: 'タスク' },
  { href: '/admin/scores', label: 'スコア' },
  { href: '/admin/sites', label: 'サイト生成' },
  { href: '/admin/send', label: 'MORM送信' },
  { href: '/admin/rewards', label: 'MORM履歴' },
  { href: '/admin/connections', label: '接続管理' },
  { href: '/admin/designs', label: 'デザイン' },
  { href: '/admin/ads', label: '広告管理' },
  { href: '/admin/chat', label: 'チャット' },
];

export default function AdminLayout({ children }) {
  const pathname = usePathname();

  return (
    <div>
      <nav style={{
        background: 'rgba(12, 12, 29, 0.92)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        height: 52,
        padding: '0 16px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        overflowX: 'auto',
        scrollbarWidth: 'none',
      }}>
        <style>{`nav::-webkit-scrollbar{display:none}`}</style>

        <Link href="/admin/dashboard" style={{
          display: 'flex', alignItems: 'center', gap: 6,
          marginRight: 12, flexShrink: 0, textDecoration: 'none',
        }}>
          <img src="/icons/logo.svg" width={22} height={22} alt="" />
          <span style={{
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            fontWeight: 800, fontSize: 14,
          }}>Dashboard</span>
          <span style={{
            background: '#667eea', color: '#fff',
            fontSize: 8, fontWeight: 700,
            padding: '1px 5px', borderRadius: 3,
          }}>ADMIN</span>
        </Link>

        {NAV.map(item => {
          const active = pathname?.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} style={{
              fontSize: 11.5, textDecoration: 'none', whiteSpace: 'nowrap',
              padding: '0 8px', height: 52, flexShrink: 0,
              display: 'inline-flex', alignItems: 'center',
              color: active ? '#e2e8f0' : 'rgba(255,255,255,0.4)',
              fontWeight: active ? 600 : 400,
              borderBottom: active ? '2px solid #667eea' : '2px solid transparent',
              transition: 'color 0.15s',
            }}>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="container" style={{ paddingTop: 20 }}>{children}</div>
    </div>
  );
}

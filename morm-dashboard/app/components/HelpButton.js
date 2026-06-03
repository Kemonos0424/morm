'use client';

import { useState } from 'react';

export default function HelpButton({ title, children }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        style={{
          width: 22, height: 22, borderRadius: '50%',
          background: 'rgba(102,126,234,0.15)', border: '1px solid rgba(102,126,234,0.3)',
          color: '#667eea', fontSize: 12, fontWeight: 700,
          cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, marginLeft: 6,
        }}
        title="ヘルプ"
      >?</button>

      {open && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', zIndex: 10000,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        }} onClick={() => setOpen(false)}>
          <div style={{
            maxWidth: 500, width: '100%', maxHeight: '80vh', overflowY: 'auto',
            background: '#14142b', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: 28,
            boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: '#667eea' }}>?</span> {title}
              </h3>
              <button onClick={() => setOpen(false)} style={{
                background: 'none', border: 'none', color: 'var(--text-muted)',
                fontSize: 20, cursor: 'pointer', padding: '4px 8px',
              }}>✕</button>
            </div>
            <div style={{ color: 'rgba(255,255,255,0.75)', fontSize: 14, lineHeight: 1.8 }}>
              {children}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

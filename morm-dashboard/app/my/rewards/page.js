'use client';

import { useState, useEffect } from 'react';
import HelpButton from '@/app/components/HelpButton';

export default function RewardsPage() {
  const [address, setAddress] = useState('');
  const [claims, setClaims] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const addr = localStorage.getItem('wallet_address');
    if (addr) {
      setAddress(addr);
      fetchClaims(addr);
    }
  }, []);

  async function fetchClaims(addr) {
    try {
      const res = await fetch(`/api/my/claim?address=${addr}`);
      const data = await res.json();
      setClaims(data.claims || []);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  async function claimReward(weekLabel) {
    alert(`Claim機能はMORM L1 のリワード分配経由で実行されます。\nWeek: ${weekLabel}\n受取はパスキー署名で確定します（m0r ネイティブトークン）。`);
  }

  return (
    <div>
      <div style={{textAlign:'center',marginBottom:16}}>
        <img src="/icons/claim-illustration.svg" width={120} height={120} alt="" style={{opacity:0.85}} />
      </div>
      <h1 style={{display:'flex',alignItems:'center',gap:8}}><img src="/icons/morm-token.svg" width={32} height={32} alt="" />MORM Claim <HelpButton title="MORM Claimについて"><p>週次のスコアに応じて MORM（m0r）トークンが MORM L1 のリワードツリーに記録されます。</p><p>Claimボタンを押すとパスキー署名でトークンを受け取れます。</p><p>MORM L1 はネイティブ手数料が極小のため、ガス代はほぼ発生しません。</p><p><strong>分配方式:</strong> 運営コスト極小、ユーザーはClaim時に署名するだけです。</p></HelpButton></h1>
      <p className="text-muted text-sm mb-2" style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{address}</p>

      <div className="alert info mb-2" style={{display:'flex',alignItems:'center',gap:8}}>
        <img src="/icons/merkle-icon.svg" width={24} height={24} alt="" />
        <span><strong>MORM L1 分配方式</strong> - 運営コスト極小。Claim はパスキー署名のみ。</span>
      </div>

      <div className="card mb-2">
        <h3>トークン情報</h3>
        <table>
          <tbody>
            <tr><td className="text-muted">Token</td><td>MORM（$MORM）</td></tr>
            <tr><td className="text-muted">Unit</td><td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>m0r</td></tr>
            <tr><td className="text-muted">Network</td><td>MORM L1 (Proof of Useful Work)</td></tr>
          </tbody>
        </table>
      </div>

      <h2>Claimable Rewards</h2>
      {loading ? (
        <p className="text-muted">読み込み中...</p>
      ) : claims.length === 0 ? (
        <p className="text-muted text-center mt-2">Claim可能なリワードはありません</p>
      ) : (
        <table>
          <thead>
            <tr><th>週</th><th>MORM量</th><th>L1 Proof</th><th>ステータス</th><th></th></tr>
          </thead>
          <tbody>
            {claims.map((c, i) => (
              <tr key={i}>
                <td>{c.week}</td>
                <td style={{ color: 'var(--yellow)', fontWeight: 700, display:'flex',alignItems:'center',gap:4 }}><img src="/icons/morm-token-sm.svg" width={16} height={16} alt="" />{c.amount} MORM</td>
                <td className="text-sm text-muted">{c.proofCount} proofs</td>
                <td><span className={`badge ${c.claimed ? 'green' : 'yellow'}`}>{c.claimed ? 'Claimed' : 'Unclaimed'}</span></td>
                <td>
                  {!c.claimed && (
                    <button className="btn-primary btn-sm" onClick={() => claimReward(c.week)}>Claim</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

import { redirect } from 'next/navigation';

// api.morm.one はウォレットAPI（account.html が使う /api/wallet/*）と Agent Lane
// (/api/lane・/api/ads) の API ホスト。旧 0x/localStorage の運用者ダッシュボードは
// node.morm.one（MORMNODE）に統合済みのため、ルートアクセスはそちらへ誘導する。
export default function Home() {
  redirect('https://node.morm.one');
}

import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';

export async function POST(request) {
  const { password } = await request.json();
  const adminPass = (process.env.ADMIN_PASSWORD || '').trim();
  // fail-closed: ADMIN_PASSWORD 未設定なら管理ログイン無効（既定 '1234' 撤廃）。
  if (!adminPass) {
    console.warn('[auth/admin] ADMIN_PASSWORD not set — admin login disabled.');
    return NextResponse.json({ error: '管理者ログインは未設定です（ADMIN_PASSWORD を設定してください）' }, { status: 503 });
  }
  if (password === adminPass) {
    return NextResponse.json({ success: true });
  }
  return NextResponse.json({ error: 'パスワードが正しくありません' }, { status: 401 });
}

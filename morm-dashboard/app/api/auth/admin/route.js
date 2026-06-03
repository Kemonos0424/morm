import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';

export async function POST(request) {
  const { password } = await request.json();
  const adminPass = (process.env.ADMIN_PASSWORD || '1234').trim();
  if (password === adminPass) {
    return NextResponse.json({ success: true });
  }
  return NextResponse.json({ error: 'パスワードが正しくありません' }, { status: 401 });
}

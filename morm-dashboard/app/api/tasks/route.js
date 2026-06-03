import { NextResponse } from 'next/server';
import { dbAll, dbGet, dbRun } from '@/app/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const tasks = await dbAll('SELECT * FROM tasks ORDER BY category, id');
    return NextResponse.json({ tasks });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const { id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec } = await request.json();
    if (!id || !category || !name) {
      return NextResponse.json({ error: 'id, category, name は必須です' }, { status: 400 });
    }

    const existing = await dbGet('SELECT * FROM tasks WHERE id = ?', [id]);
    if (existing) {
      return NextResponse.json({ error: 'このIDは既に使われています' }, { status: 400 });
    }

    await dbRun(
      `INSERT INTO tasks (id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, category, name, description || '', score_value || 10, auto || 0, morm_cost || 0, requires_credential || null, auto_trigger || null, cooldown_hours || 0, command || null, timeout_sec || 300]
    );

    return NextResponse.json({ success: true, id });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function PUT(request) {
  try {
    const { id, category, name, description, score_value, auto, morm_cost, requires_credential, auto_trigger, cooldown_hours, command, timeout_sec } = await request.json();
    if (!id) return NextResponse.json({ error: 'id は必須です' }, { status: 400 });

    await dbRun(
      `UPDATE tasks SET category=?, name=?, description=?, score_value=?, auto=?, morm_cost=?, requires_credential=?, auto_trigger=?, cooldown_hours=?, command=?, timeout_sec=?
       WHERE id=?`,
      [category, name, description || '', score_value || 10, auto || 0, morm_cost || 0, requires_credential || null, auto_trigger || null, cooldown_hours || 0, command || null, timeout_sec || 300, id]
    );

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');
    if (!id) return NextResponse.json({ error: 'id は必須です' }, { status: 400 });

    await dbRun('DELETE FROM task_runs WHERE task_id = ?', [id]);
    await dbRun('DELETE FROM tasks WHERE id = ?', [id]);

    return NextResponse.json({ success: true });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

import { NextResponse } from 'next/server';
import { dbGet, dbRun } from '@/app/lib/db';
import { calcBaseScore } from '@/app/lib/scoring';
import os from 'os';

export const dynamic = 'force-dynamic';
export async function POST(request) {
  const { nodeId } = await request.json();
  if (!nodeId) return NextResponse.json({ error: 'nodeId required' }, { status: 400 });

  const node = await dbGet('SELECT * FROM nodes WHERE id = ?', [nodeId]);
  if (!node) return NextResponse.json({ error: 'ノードが見つかりません' }, { status: 404 });

  let specs;

  // For local/self check
  if (!node.ssh_host || node.ssh_host === 'localhost' || node.ssh_host === '127.0.0.1') {
    const cpuCores = os.cpus().length;
    const ramGb = Math.round(os.totalmem() / (1024 ** 3) * 10) / 10;
    const storageGb = 500; // placeholder
    specs = { cpu_cores: cpuCores, ram_gb: ramGb, storage_gb: storageGb };
  } else {
    // For remote, expect ssh script - simulate for now
    specs = { cpu_cores: node.cpu_cores, ram_gb: node.ram_gb, storage_gb: node.storage_gb };
  }

  const baseScore = calcBaseScore(specs.cpu_cores, specs.ram_gb, specs.storage_gb);
  const totalScore = baseScore + (node.task_score || 0);

  await dbRun(`
    UPDATE nodes SET cpu_cores = ?, ram_gb = ?, storage_gb = ?, base_score = ?, total_score = ?
    WHERE id = ?
  `, [specs.cpu_cores, specs.ram_gb, specs.storage_gb, baseScore, totalScore, nodeId]);

  return NextResponse.json({ specs: { ...specs, base_score: baseScore, total_score: totalScore } });
}

#!/bin/bash
#============================================================
# ノードスペック取得スクリプト (MacBookから実行)
# 各ノードにSSH → スペック取得 → Turso DBに直接書き込み
# Usage: bash scripts/update-specs.sh
#============================================================
set -e
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"

echo "=== Node Spec Updater ==="

# Load env
if [ -f .env.local ]; then
  export $(grep -v '^#' .env.local | xargs)
fi

# Function: get specs from a node via SSH
get_specs() {
  local HOST=$1 PORT=$2 USER=$3 PASS=$4 NODE_ID=$5

  echo "Checking $NODE_ID ($USER@$HOST:$PORT)..."

  local RESULT
  RESULT=$(expect << EXPEOF 2>&1
set timeout 15
spawn ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 $USER@$HOST -p $PORT
expect {
  "password:" { send "$PASS\r"; exp_continue }
  "%" {}
  "\\\$ " {}
  timeout { puts "TIMEOUT"; exit 1 }
}
send "echo SPEC_START\r"
expect "SPEC_START"
send "echo CPUS=\$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 0)\r"
expect "%\|\\$"
send "echo RAMBYTES=\$(sysctl -n hw.memsize 2>/dev/null || echo 0)\r"
expect "%\|\\$"
send "echo RAMFREE=\$(free -b 2>/dev/null | awk '/Mem/{print \\\$2}' || echo 0)\r"
expect "%\|\\$"
send "echo DISK=\$(df -g / 2>/dev/null | tail -1 | awk '{print \\\$2,\\\$3}' || df -BG / 2>/dev/null | tail -1 | awk '{gsub(/G/,\\\"\\\"); print \\\$2,\\\$3}')\r"
expect "%\|\\$"
send "echo OSNAME=\$(uname -s)\r"
expect "%\|\\$"
send "echo KERNEL=\$(uname -r)\r"
expect "%\|\\$"
send "echo HNAME=\$(hostname)\r"
expect "%\|\\$"
send "echo CHIP=\$(sysctl -n machdep.cpu.brand_string 2>/dev/null || lscpu 2>/dev/null | grep 'Model name' | sed 's/.*: //' || echo unknown)\r"
expect "%\|\\$"
send "echo SPEC_END\r"
expect "SPEC_END"
send "exit\r"
expect eof
EXPEOF
  )

  # Parse results
  local CPUS=$(echo "$RESULT" | grep -oP 'CPUS=\K\d+' | head -1)
  local RAMBYTES=$(echo "$RESULT" | grep -oP 'RAMBYTES=\K\d+' | head -1)
  local RAMFREE=$(echo "$RESULT" | grep -oP 'RAMFREE=\K\d+' | head -1)
  local DISK=$(echo "$RESULT" | grep -oP 'DISK=\K[\d ]+' | head -1)
  local OSNAME=$(echo "$RESULT" | grep -oP 'OSNAME=\K\S+' | head -1)
  local KERNEL=$(echo "$RESULT" | grep -oP 'KERNEL=\K\S+' | head -1)
  local HNAME=$(echo "$RESULT" | grep -oP 'HNAME=\K\S+' | head -1)
  local CHIP=$(echo "$RESULT" | grep 'CHIP=' | sed 's/.*CHIP=//' | head -1 | tr -d '\r')

  # Calculate RAM in GB
  local RAM_GB=0
  if [ -n "$RAMBYTES" ] && [ "$RAMBYTES" -gt 0 ] 2>/dev/null; then
    RAM_GB=$(echo "$RAMBYTES / 1073741824" | bc)
  elif [ -n "$RAMFREE" ] && [ "$RAMFREE" -gt 0 ] 2>/dev/null; then
    RAM_GB=$(echo "$RAMFREE / 1073741824" | bc)
  fi

  local DISK_TOTAL=$(echo "$DISK" | awk '{print $1}')
  local DISK_USED=$(echo "$DISK" | awk '{print $2}')

  [ -z "$CPUS" ] && CPUS=0
  [ -z "$RAM_GB" ] && RAM_GB=0
  [ -z "$DISK_TOTAL" ] && DISK_TOTAL=0
  [ -z "$DISK_USED" ] && DISK_USED=0

  echo "  CPU: ${CPUS}コア, RAM: ${RAM_GB}GB, Disk: ${DISK_TOTAL}GB (使用${DISK_USED}GB)"
  echo "  OS: $OSNAME $KERNEL, Host: $HNAME, Chip: $CHIP"

  # Update Turso DB
  node -e "
    import { createClient } from '@libsql/client';
    const client = createClient({
      url: process.env.TURSO_DATABASE_URL.trim(),
      authToken: process.env.TURSO_AUTH_TOKEN.trim()
    });
    async function main() {
      const cpus = ${CPUS:-0};
      const ram = ${RAM_GB:-0};
      const disk = ${DISK_TOTAL:-0};
      const used = ${DISK_USED:-0};
      const base = Math.round(cpus * 10 + ram * 5 + disk * 0.1);
      await client.execute({
        sql: 'UPDATE nodes SET cpu_cores=?, ram_gb=?, storage_gb=?, storage_used_gb=?, base_score=?, total_score=?+task_score, status=\"online\", last_heartbeat=datetime(\"now\") WHERE id=?',
        args: [cpus, ram, disk, used, base, base, '${NODE_ID}']
      });
      const r = await client.execute({sql:'SELECT id,cpu_cores,ram_gb,storage_gb,base_score,total_score FROM nodes WHERE id=?',args:['${NODE_ID}']});
      console.log('  Updated:', JSON.stringify(r.rows[0]));
    }
    main().catch(e => console.error('  DB Error:', e.message));
  " 2>&1 | grep -v 'injected env'
}

# Update Mac Mini (via LAN)
get_specs "192.168.2.122" "22" "user" "9999" "mac_mini"

# Update claude_pc1 (if reachable)
echo ""
get_specs "221.241.79.54" "22222" "claude_pc1" "redm/2026" "claude_pc1" 2>/dev/null || echo "  claude_pc1: 接続できませんでした"

echo ""
echo "=== Done ==="

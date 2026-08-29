#!/bin/bash
# Run every agent-lane verification sequentially and summarize pass/fail.
# Each suite boots its own ephemeral L1 (+ isolated Next dev where needed),
# verifies on a real chain, and tears down. NEVER touches prod (port 8900).
cd "$(dirname "$0")" || exit 1

# name : command  (phase0 is a self-contained python script; rest are runners)
SUITES=(
  "P0  agent-earn      : python3 phase0_agent_earn.py"
  "P1  lane-api        : bash phase1_run.sh"
  "P2a units           : bash phase2_units_run.sh"
  "P2b proportional    : bash phase2_prop_run.sh"
  "P2c cashout-valve   : bash phase2_valve_run.sh"
  "P2d view_by_other   : bash phase2_view_run.sh"
  "P2e node-emission   : bash phase2_node_run.sh"
  "P2f ad-escrow       : bash phase2_ads_run.sh"
  "P2g signed-watch    : node phase2_signedwatch_sign.mjs | python3 phase2_signedwatch_verify.py"
)

pass=0; fail=0; results=()
for entry in "${SUITES[@]}"; do
  name="${entry%%:*}"; cmd="${entry#*: }"
  echo; echo "########## RUN ${name} :: ${cmd} ##########"
  if eval "$cmd" > "/tmp/agentlane_${name// /_}.log" 2>&1; then
    echo "PASS ${name}"; results+=("PASS ${name}"); pass=$((pass+1))
  else
    echo "FAIL ${name} (see /tmp/agentlane_${name// /_}.log)"; results+=("FAIL ${name}"); fail=$((fail+1))
  fi
done

echo; echo "================= SUMMARY ================="
for r in "${results[@]}"; do echo "  $r"; done
echo "  ${pass} passed, ${fail} failed"
[ "$fail" -eq 0 ]

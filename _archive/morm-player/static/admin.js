// MORM Admin — network overview + invite generator.
//
// Phase 30g: all L1 reads route through the gateway's /api/admin/*
// proxies so the page works in Docker compose where the browser can't
// reach the L1's internal port directly.

const GATEWAY_URL = window.location.origin;
const $ = id => document.getElementById(id);

async function refresh() {
  try {
    const info = await fetch(`${GATEWAY_URL}/api/admin/info`).then(r => r.json());
    $('net-head').textContent  = info.head_height;
    $('net-final').textContent = info.finalized_height;
    $('net-depth').textContent = info.finality_depth;
    $('net-treas').textContent = info.treasury;
    $('net-root').textContent  = info.state_root.slice(0, 32) + '…';
    $('net-tips').textContent  = info.tips.map(t => t.slice(0, 14) + '…').join(', ');

    const tbody = $('prod-table').querySelector('tbody');
    tbody.innerHTML = '';
    for (const p of info.producers) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${p.name}</td>
        <td class="addr">${p.address}</td>
        <td>${p.weight}</td>
        <td>${p.completed}</td>`;
      tbody.appendChild(tr);
    }
    if (!info.producers.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted)">no producers registered yet</td></tr>';
    }
    // Phase 24-UI: render producers as a swarm map around the self node.
    renderSwarm(info.producers || []);
  } catch (e) {
    $('net-head').textContent = `error: ${e.message}`;
  }
}

async function showBootstrap() {
  const j = await fetch(`${GATEWAY_URL}/api/admin/bootstrap`).then(r => r.json());
  $('invite-out').textContent = JSON.stringify(j, null, 2);
}

function makeInvite() {
  const target = $('invite-target').value.trim();
  if (!target) {
    $('invite-out').textContent = 'enter an SSH target first (e.g. user@192.168.2.123)';
    return;
  }
  const name = $('invite-name').value.trim() || target.replace(/[@.:]/g, '_');
  // The shell command runs from the host machine's morm-l1 dir.
  const cmd = `# run on the host with morm-l1/ checked out:
cd ~/Desktop/MORM/morm-l1
ops/invite-node.sh "${target}" --name "${name}"

# this will:
#  1. ssh ${target}, ensure python3.11+ + ffmpeg
#  2. rsync morm-l1/ → ${target}:~/MORM/morm-l1
#  3. install LaunchAgent (macOS) or systemd unit (Linux), peering this host
#  4. generate ed25519 producer key on ${target}
#  5. submit a treasury-signed REGISTER_PRODUCER tx so it joins slot rotation`;
  $('invite-out').textContent = cmd;
}

$('btn-bootstrap').addEventListener('click', showBootstrap);
$('btn-make').addEventListener('click', makeInvite);

// ── Phase 30g: peer discovery + producer registration ───────────────────
async function refreshPeerDiscovery() {
  const tbody = document.querySelector('#peers-table tbody');
  const summary = document.getElementById('peers-summary');
  try {
    const r = await fetch(`${GATEWAY_URL}/api/admin/peer-discovery`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    summary.textContent =
      `${d.summary.alive}/${d.summary.total} alive` +
      (d.public_url ? ` · self=${d.public_url}` : '');
    if (!d.peers.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="color:var(--muted)">no peers — fresh node, running standalone</td></tr>';
      return;
    }
    tbody.innerHTML = '';
    for (const p of d.peers) {
      const tr = document.createElement('tr');
      const dot = p.alive ? '<span style="color:#5fffa1">●</span>' : '<span style="color:#ff8080">●</span>';
      const headTxt = p.alive ? p.head_height : (p.error || '—');
      const rttTxt = p.alive ? `${p.ms} ms` : '—';
      tr.innerHTML = `
        <td><span style="background:rgba(77,210,255,0.1);border:1px solid rgba(77,210,255,0.3);padding:1px 6px;border-radius:4px;font-size:10px">${p.source}</span></td>
        <td class="addr" style="font-size:11px">${p.url}</td>
        <td>${dot} ${p.alive ? 'OK' : 'unreachable'}</td>
        <td>${headTxt}</td>
        <td style="font-size:11px;color:var(--muted)">${p.state_root || '—'}</td>
        <td>${rttTxt}</td>`;
      tbody.appendChild(tr);
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:#ff8080">error: ${e.message}</td></tr>`;
  }
}

async function refreshRegistration() {
  try {
    const r = await fetch(`${GATEWAY_URL}/api/admin/registration-template`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    $('reg-pub').textContent  = d.producer_pubkey  || '— (no L1 producer key on this node)';
    $('reg-addr').textContent = d.producer_address || '—';
    if (d.already_registered === true) {
      $('reg-state').innerHTML = '<span style="color:#5fffa1">✓ registered (in producers list)</span>';
    } else if (d.already_registered === false) {
      $('reg-state').innerHTML = '<span style="color:#ffd540">pending — needs treasury approval</span>';
    } else {
      $('reg-state').textContent = '?';
    }
    $('reg-template').textContent = JSON.stringify(d.template, null, 2)
      + '\n\n# instructions\n# ' + d.instructions.join('\n# ');
  } catch (e) {
    $('reg-template').textContent = `error: ${e.message}`;
  }
}

$('btn-copy-reg').addEventListener('click', () => {
  const text = $('reg-template').textContent;
  navigator.clipboard.writeText(text).then(
    () => {
      $('btn-copy-reg').textContent = '✓ copied';
      setTimeout(() => $('btn-copy-reg').textContent = '📋 copy JSON', 1500);
    },
    () => { $('btn-copy-reg').textContent = '⚠ copy failed'; }
  );
});

refreshPeerDiscovery();
refreshRegistration();
setInterval(refreshPeerDiscovery, 10_000);
setInterval(refreshRegistration, 15_000);

// ── Phase 24-UI: Swarm Map renderer ────────────────────────────────────
// Lays each producer on a ring around (400,160), connected by dashed
// "gossip" edges to the self node. Pulses animate via CSS.
const SVG_NS = 'http://www.w3.org/2000/svg';
function renderSwarm(producers) {
  const nodesG = document.getElementById('swarm-nodes');
  const edgesG = document.getElementById('swarm-edges');
  if (!nodesG || !edgesG) return;
  nodesG.innerHTML = ''; edgesG.innerHTML = '';
  const cx = 400, cy = 160;
  const R  = 110;
  const N  = Math.max(producers.length, 1);
  producers.forEach((p, i) => {
    const angle = (i / N) * Math.PI * 2 - Math.PI / 2;
    const x = cx + R * Math.cos(angle);
    const y = cy + R * Math.sin(angle);
    // edge first so node sits on top
    const line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('class', 'swarm-edge');
    line.setAttribute('x1', cx); line.setAttribute('y1', cy);
    line.setAttribute('x2', x);  line.setAttribute('y2', y);
    line.style.animationDelay = `${(i * 0.7) % 6}s`;
    edgesG.appendChild(line);

    const node = document.createElementNS(SVG_NS, 'circle');
    node.setAttribute('class', 'swarm-node');
    node.setAttribute('cx', x); node.setAttribute('cy', y);
    node.setAttribute('r',  4 + Math.min(p.weight || 1, 6));
    node.setAttribute('aria-label', `${p.name} (${p.address})`);
    nodesG.appendChild(node);

    const pulse = document.createElementNS(SVG_NS, 'circle');
    pulse.setAttribute('class', 'swarm-pulse');
    pulse.setAttribute('cx', x); pulse.setAttribute('cy', y);
    pulse.setAttribute('r', 4);
    pulse.style.animationDelay = `${(i * 0.5) % 3}s`;
    nodesG.appendChild(pulse);

    // small label
    const label = document.createElementNS(SVG_NS, 'text');
    label.setAttribute('x', x); label.setAttribute('y', y - 12);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('font-size', '9');
    label.setAttribute('fill', 'rgba(232,232,240,0.7)');
    label.setAttribute('font-family', 'Menlo, monospace');
    label.textContent = p.name || p.address.slice(0, 10);
    nodesG.appendChild(label);
  });
}

refresh();
setInterval(refresh, 5000);

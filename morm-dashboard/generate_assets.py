#!/usr/bin/env python3
"""
Node Dashboard 全画像素材生成 (~45個)
- SVG: XML直接記述（正確・軽量・スケーラブル）
- PNG: Gemini生成（hero-bg, og-image）

Usage:
    python generate_assets.py              # 全素材生成
    python generate_assets.py --group svg  # SVGのみ
    python generate_assets.py --group png  # PNGのみ
"""

import argparse
import os
import sys
import time
from pathlib import Path

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY", "AIzaSyClUYJDJyL0C1w5O5xqrG2brXD58WT8_1U"
)
GEMINI_MODEL = "gemini-3.1-flash-image-preview"

BASE = Path(__file__).parent
ICONS_DIR = BASE / "public" / "icons"
PUBLIC_DIR = BASE / "public"

# ─── カラー ──────────────────────────────────────────────
P = "#8b5cf6"    # purple
B = "#3b82f6"    # blue
C = "#06b6d4"    # cyan
G = "#22c55e"    # green
O = "#f97316"    # orange
R = "#ef4444"    # red
PK = "#ec4899"   # pink
Y = "#eab308"    # yellow
GR = "#6b7280"   # gray
W = "#ffffff"    # white
GOLD = "#eab308"


def svg(w, h, content, vb=None):
    """SVGラッパー"""
    viewbox = vb or f"0 0 {w} {h}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="{viewbox}" fill="none">\n'
        f'  <defs>\n'
        f'    <linearGradient id="gp" x1="0" y1="0" x2="1" y2="1">\n'
        f'      <stop offset="0%" stop-color="{P}"/>\n'
        f'      <stop offset="100%" stop-color="{B}"/>\n'
        f'    </linearGradient>\n'
        f'  </defs>\n'
        f'{content}\n'
        f'</svg>'
    )


# ═════════════════════════════════════════════════════════
# 1. LOGO & BRAND
# ═════════════════════════════════════════════════════════

def gen_logo():
    """1-1: logo.svg 40x40 — 3ノードネットワーク"""
    return svg(40, 40, '''
  <circle cx="12" cy="10" r="5" fill="url(#gp)" opacity="0.9"/>
  <circle cx="28" cy="10" r="5" fill="url(#gp)" opacity="0.9"/>
  <circle cx="20" cy="30" r="5" fill="url(#gp)" opacity="0.9"/>
  <line x1="12" y1="10" x2="28" y2="10" stroke="url(#gp)" stroke-width="1.5" opacity="0.6"/>
  <line x1="12" y1="10" x2="20" y2="30" stroke="url(#gp)" stroke-width="1.5" opacity="0.6"/>
  <line x1="28" y1="10" x2="20" y2="30" stroke="url(#gp)" stroke-width="1.5" opacity="0.6"/>
''')


def gen_logo_full():
    """1-2: logo-full.svg 200x40 — ロゴ+テキスト"""
    return svg(200, 40, '''
  <circle cx="12" cy="12" r="4" fill="url(#gp)"/>
  <circle cx="24" cy="12" r="4" fill="url(#gp)"/>
  <circle cx="18" cy="26" r="4" fill="url(#gp)"/>
  <line x1="12" y1="12" x2="24" y2="12" stroke="url(#gp)" stroke-width="1.2" opacity="0.5"/>
  <line x1="12" y1="12" x2="18" y2="26" stroke="url(#gp)" stroke-width="1.2" opacity="0.5"/>
  <line x1="24" y1="12" x2="18" y2="26" stroke="url(#gp)" stroke-width="1.2" opacity="0.5"/>
  <text x="42" y="25" font-family="system-ui,-apple-system,sans-serif" font-size="16" font-weight="700" fill="url(#gp)">Node Dashboard</text>
''')


# ═════════════════════════════════════════════════════════
# 2. TOP PAGE
# ═════════════════════════════════════════════════════════

def gen_wallet_icon():
    """2-2: wallet-icon.svg"""
    return svg(48, 48, f'''
  <rect x="6" y="12" width="30" height="24" rx="4" stroke="url(#gp)" stroke-width="2" fill="none"/>
  <path d="M6 18h30" stroke="url(#gp)" stroke-width="1.5"/>
  <circle cx="30" cy="26" r="3" fill="url(#gp)"/>
  <path d="M36 24l5-5M41 19v5h-5" stroke="{C}" stroke-width="1.5" stroke-linecap="round"/>
''')


def gen_network_illustration():
    """2-3: network-illustration.svg"""
    return svg(400, 300, f'''
  <!-- Central token -->
  <circle cx="200" cy="150" r="25" fill="url(#gp)" opacity="0.3"/>
  <text x="200" y="156" text-anchor="middle" font-family="monospace" font-size="14" font-weight="700" fill="{W}">CLT</text>
  <!-- Nodes -->
  <rect x="50" y="60" width="40" height="30" rx="4" stroke="{P}" stroke-width="1.5" fill="none" opacity="0.7"/>
  <rect x="50" y="55" width="40" height="5" rx="2" fill="{P}" opacity="0.4"/>
  <rect x="310" y="60" width="40" height="30" rx="4" stroke="{B}" stroke-width="1.5" fill="none" opacity="0.7"/>
  <rect x="310" y="55" width="40" height="5" rx="2" fill="{B}" opacity="0.4"/>
  <rect x="50" y="210" width="40" height="30" rx="4" stroke="{C}" stroke-width="1.5" fill="none" opacity="0.7"/>
  <rect x="50" y="205" width="40" height="5" rx="2" fill="{C}" opacity="0.4"/>
  <rect x="310" y="210" width="40" height="30" rx="4" stroke="{G}" stroke-width="1.5" fill="none" opacity="0.7"/>
  <rect x="310" y="205" width="40" height="5" rx="2" fill="{G}" opacity="0.4"/>
  <!-- Lines -->
  <line x1="90" y1="75" x2="175" y2="150" stroke="{P}" stroke-width="1" opacity="0.3"/>
  <line x1="310" y1="75" x2="225" y2="150" stroke="{B}" stroke-width="1" opacity="0.3"/>
  <line x1="90" y1="225" x2="175" y2="150" stroke="{C}" stroke-width="1" opacity="0.3"/>
  <line x1="310" y1="225" x2="225" y2="150" stroke="{G}" stroke-width="1" opacity="0.3"/>
''')


# ═════════════════════════════════════════════════════════
# 3. MY PAGE — Profile & Node
# ═════════════════════════════════════════════════════════

def gen_avatar_default():
    return svg(64, 64, f'''
  <circle cx="32" cy="32" r="30" fill="url(#gp)" opacity="0.2"/>
  <circle cx="32" cy="24" r="10" fill="url(#gp)" opacity="0.6"/>
  <path d="M14 52c0-10 8-18 18-18s18 8 18 18" fill="url(#gp)" opacity="0.4"/>
''')


def gen_node_online():
    return svg(32, 32, f'''
  <circle cx="16" cy="16" r="6" fill="{G}"/>
  <circle cx="16" cy="16" r="10" fill="{G}" opacity="0.2"/>
  <circle cx="16" cy="16" r="14" fill="{G}" opacity="0.08"/>
''')


def gen_node_offline():
    return svg(32, 32, f'''
  <circle cx="16" cy="16" r="6" fill="{GR}" opacity="0.5"/>
  <circle cx="16" cy="16" r="10" fill="{GR}" opacity="0.1"/>
''')


def gen_pc_icon():
    return svg(48, 48, f'''
  <rect x="8" y="6" width="32" height="24" rx="3" stroke="url(#gp)" stroke-width="2" fill="none"/>
  <line x1="18" y1="30" x2="18" y2="38" stroke="url(#gp)" stroke-width="1.5"/>
  <line x1="30" y1="30" x2="30" y2="38" stroke="url(#gp)" stroke-width="1.5"/>
  <line x1="12" y1="38" x2="36" y2="38" stroke="url(#gp)" stroke-width="2" stroke-linecap="round"/>
  <circle cx="24" cy="18" r="2" fill="url(#gp)" opacity="0.5"/>
''')


def gen_macmini_icon():
    return svg(48, 48, f'''
  <rect x="6" y="18" width="36" height="12" rx="3" stroke="{GR}" stroke-width="1.5" fill="none" opacity="0.7"/>
  <line x1="6" y1="26" x2="42" y2="26" stroke="{GR}" stroke-width="0.5" opacity="0.3"/>
  <circle cx="36" cy="24" r="1.5" fill="{GR}" opacity="0.5"/>
''')


# ═════════════════════════════════════════════════════════
# 4. SERVICE ICONS (8個)
# ═════════════════════════════════════════════════════════

def _svc(content):
    return svg(24, 24, content)

def gen_svc_x():
    return _svc(f'<path d="M4 4l6.5 8L4 20h2l5.2-6.4L15.5 20H20l-6.8-8.3L19.5 4H17.5l-4.8 5.9L8.5 4H4z" fill="{W}"/>')

def gen_svc_instagram():
    return _svc(f'''
  <defs><linearGradient id="ig" x1="0" y1="1" x2="1" y2="0"><stop offset="0%" stop-color="{Y}"/><stop offset="50%" stop-color="{R}"/><stop offset="100%" stop-color="{PK}"/></linearGradient></defs>
  <rect x="3" y="3" width="18" height="18" rx="5" stroke="url(#ig)" stroke-width="2" fill="none"/>
  <circle cx="12" cy="12" r="4.5" stroke="url(#ig)" stroke-width="2" fill="none"/>
  <circle cx="17.5" cy="6.5" r="1.2" fill="url(#ig)"/>
''')

def gen_svc_tiktok():
    return _svc(f'''
  <path d="M9 3v12a3 3 0 106-0V3" stroke="{W}" stroke-width="2" fill="none"/>
  <path d="M15 3c0 3 3 4 5 4" stroke="{C}" stroke-width="2" fill="none"/>
  <path d="M9 15a3 3 0 01-3-3" stroke="{PK}" stroke-width="2" fill="none"/>
''')

def gen_svc_facebook():
    return _svc(f'<path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z" fill="#1877F2"/>')

def gen_svc_youtube():
    return _svc(f'''
  <rect x="2" y="5" width="20" height="14" rx="4" fill="{R}"/>
  <polygon points="10,8 16,12 10,16" fill="{W}"/>
''')

def gen_svc_gmail():
    return _svc(f'''
  <rect x="3" y="5" width="18" height="14" rx="2" stroke="{R}" stroke-width="1.5" fill="none"/>
  <polyline points="3,5 12,13 21,5" stroke="{R}" stroke-width="1.5" fill="none"/>
''')

def gen_svc_github():
    return _svc(f'<path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.1.39-1.99 1.03-2.69-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02A9.56 9.56 0 0112 6.8c.85.004 1.71.115 2.51.34 1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.6 1.03 2.69 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.16.59.67.5A10.013 10.013 0 0022 12c0-5.523-4.477-10-10-10z" fill="{W}"/>')

def gen_svc_cloudflare():
    return _svc(f'''
  <path d="M16 14l1.2-4.2c.2-.6-.1-1.2-.7-1.4l-1-.3C14.8 5.8 12.7 4 10.3 4 7.4 4 5 6.2 4.6 9.1 3.7 9.5 3 10.4 3 11.5c0 1.4 1.1 2.5 2.5 2.5H16z" fill="{O}"/>
  <path d="M18 10c-.4 0-.7.1-1 .2l.5-1.7c.1-.4-.1-.8-.5-.9l-.5-.2c-.7-1.5-2.2-2.4-3.8-2.4" stroke="{O}" stroke-width="0" fill="{O}" opacity="0.6"/>
''')


# ═════════════════════════════════════════════════════════
# 5. TASK CATEGORY ICONS (10個)
# ═════════════════════════════════════════════════════════

def _task(content, color=None):
    return svg(32, 32, content)

def gen_task_site():
    return _task(f'''
  <rect x="4" y="4" width="24" height="20" rx="3" stroke="url(#gp)" stroke-width="1.5" fill="none"/>
  <line x1="4" y1="10" x2="28" y2="10" stroke="url(#gp)" stroke-width="1"/>
  <circle cx="8" cy="7" r="1" fill="{R}"/><circle cx="11" cy="7" r="1" fill="{Y}"/><circle cx="14" cy="7" r="1" fill="{G}"/>
''')

def gen_task_sns():
    return _task(f'''
  <path d="M6 24V10a4 4 0 014-4h8a4 4 0 014 4v8a4 4 0 01-4 4H10l-4 2z" stroke="{PK}" stroke-width="1.5" fill="none"/>
  <path d="M13 13l3 2-3 2" stroke="{PK}" stroke-width="1.5" fill="none" stroke-linecap="round"/>
''')

def gen_task_gmail():
    return _task(f'''
  <rect x="4" y="7" width="24" height="18" rx="3" stroke="{B}" stroke-width="1.5" fill="none"/>
  <polyline points="4,7 16,17 28,7" stroke="{B}" stroke-width="1.5" fill="none"/>
''')

def gen_task_git():
    return _task(f'''
  <circle cx="10" cy="8" r="3" stroke="{O}" stroke-width="1.5" fill="none"/>
  <circle cx="22" cy="14" r="3" stroke="{O}" stroke-width="1.5" fill="none"/>
  <circle cx="10" cy="24" r="3" stroke="{O}" stroke-width="1.5" fill="none"/>
  <path d="M10 11v10M13 8l6 4" stroke="{O}" stroke-width="1.5"/>
''')

def gen_task_cloudflare():
    return _task(f'''
  <path d="M8 22a6 6 0 010-12 8 8 0 0115 4h1a4 4 0 010 8H8z" stroke="{O}" stroke-width="1.5" fill="none"/>
  <path d="M14 18l2-4 2 4" stroke="{O}" stroke-width="1.5" fill="none"/>
''')

def gen_task_automation():
    return _task(f'''
  <circle cx="16" cy="16" r="9" stroke="{P}" stroke-width="1.5" fill="none"/>
  <path d="M16 10v4l3 2" stroke="{P}" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M12 4l4 3 4-3" stroke="{P}" stroke-width="1.5" fill="none" stroke-linecap="round"/>
''')

def gen_task_api():
    return _task(f'''
  <rect x="4" y="10" width="10" height="12" rx="2" stroke="{B}" stroke-width="1.5" fill="none"/>
  <rect x="18" y="10" width="10" height="12" rx="2" stroke="{B}" stroke-width="1.5" fill="none"/>
  <path d="M14 16h4" stroke="{C}" stroke-width="2" stroke-linecap="round"/>
  <circle cx="9" cy="14" r="1.5" fill="{B}"/><circle cx="23" cy="14" r="1.5" fill="{B}"/>
''')

def gen_task_p2p():
    return _task(f'''
  <circle cx="16" cy="8" r="3" fill="{G}" opacity="0.7"/>
  <circle cx="8" cy="24" r="3" fill="{G}" opacity="0.7"/>
  <circle cx="24" cy="24" r="3" fill="{G}" opacity="0.7"/>
  <line x1="16" y1="11" x2="8" y2="21" stroke="{G}" stroke-width="1" opacity="0.4"/>
  <line x1="16" y1="11" x2="24" y2="21" stroke="{G}" stroke-width="1" opacity="0.4"/>
  <line x1="8" y1="24" x2="24" y2="24" stroke="{G}" stroke-width="1" opacity="0.4"/>
''')

def gen_task_storage():
    return _task(f'''
  <ellipse cx="16" cy="10" rx="10" ry="4" stroke="{C}" stroke-width="1.5" fill="none"/>
  <path d="M6 10v12c0 2.2 4.5 4 10 4s10-1.8 10-4V10" stroke="{C}" stroke-width="1.5" fill="none"/>
  <path d="M6 16c0 2.2 4.5 4 10 4s10-1.8 10-4" stroke="{C}" stroke-width="1" opacity="0.4"/>
''')

def gen_task_review():
    return _task(f'''
  <rect x="6" y="4" width="16" height="22" rx="2" stroke="{G}" stroke-width="1.5" fill="none"/>
  <line x1="10" y1="10" x2="22" y2="10" stroke="{G}" stroke-width="1" opacity="0.4"/>
  <line x1="10" y1="14" x2="22" y2="14" stroke="{G}" stroke-width="1" opacity="0.4"/>
  <line x1="10" y1="18" x2="18" y2="18" stroke="{G}" stroke-width="1" opacity="0.4"/>
  <path d="M22 16l3 3 5-7" stroke="{G}" stroke-width="2" fill="none" stroke-linecap="round"/>
''')


# ═════════════════════════════════════════════════════════
# 6. CLT TOKEN & WEB3
# ═════════════════════════════════════════════════════════

def gen_clt_token():
    return svg(48, 48, f'''
  <circle cx="24" cy="24" r="20" fill="url(#gp)" opacity="0.15"/>
  <circle cx="24" cy="24" r="20" stroke="url(#gp)" stroke-width="2" fill="none"/>
  <circle cx="24" cy="24" r="16" stroke="url(#gp)" stroke-width="0.5" fill="none" opacity="0.3"/>
  <text x="24" y="29" text-anchor="middle" font-family="monospace" font-size="12" font-weight="700" fill="url(#gp)">CLT</text>
''')

def gen_clt_token_sm():
    return svg(20, 20, f'''
  <circle cx="10" cy="10" r="8" stroke="url(#gp)" stroke-width="1.5" fill="url(#gp)" fill-opacity="0.15"/>
  <text x="10" y="13" text-anchor="middle" font-family="monospace" font-size="6" font-weight="700" fill="url(#gp)">CLT</text>
''')

def gen_merkle_icon():
    return svg(48, 48, f'''
  <circle cx="24" cy="8" r="4" fill="url(#gp)" opacity="0.8"/>
  <circle cx="12" cy="24" r="4" fill="url(#gp)" opacity="0.6"/>
  <circle cx="36" cy="24" r="4" fill="url(#gp)" opacity="0.6"/>
  <circle cx="6" cy="40" r="3" fill="url(#gp)" opacity="0.4"/>
  <circle cx="18" cy="40" r="3" fill="url(#gp)" opacity="0.4"/>
  <circle cx="30" cy="40" r="3" fill="url(#gp)" opacity="0.4"/>
  <circle cx="42" cy="40" r="3" fill="url(#gp)" opacity="0.4"/>
  <line x1="24" y1="12" x2="12" y2="20" stroke="url(#gp)" stroke-width="1" opacity="0.3"/>
  <line x1="24" y1="12" x2="36" y2="20" stroke="url(#gp)" stroke-width="1" opacity="0.3"/>
  <line x1="12" y1="28" x2="6" y2="37" stroke="url(#gp)" stroke-width="1" opacity="0.3"/>
  <line x1="12" y1="28" x2="18" y2="37" stroke="url(#gp)" stroke-width="1" opacity="0.3"/>
  <line x1="36" y1="28" x2="30" y2="37" stroke="url(#gp)" stroke-width="1" opacity="0.3"/>
  <line x1="36" y1="28" x2="42" y2="37" stroke="url(#gp)" stroke-width="1" opacity="0.3"/>
''')

def gen_claim_illustration():
    return svg(300, 200, f'''
  <!-- Hand -->
  <path d="M120 160c0-20 15-35 30-40l20-5c10-2 15 5 15 15v30c0 10-5 15-15 15h-35c-10 0-15-5-15-15z" stroke="url(#gp)" stroke-width="2" fill="none" opacity="0.6"/>
  <!-- Coin falling -->
  <circle cx="160" cy="60" r="25" stroke="url(#gp)" stroke-width="2" fill="url(#gp)" fill-opacity="0.1"/>
  <text x="160" y="66" text-anchor="middle" font-family="monospace" font-size="14" font-weight="700" fill="url(#gp)">CLT</text>
  <!-- Glow lines -->
  <line x1="160" y1="90" x2="160" y2="110" stroke="{C}" stroke-width="1.5" opacity="0.4"/>
  <line x1="145" y1="95" x2="140" y2="105" stroke="{C}" stroke-width="1" opacity="0.3"/>
  <line x1="175" y1="95" x2="180" y2="105" stroke="{C}" stroke-width="1" opacity="0.3"/>
  <!-- Sparkles -->
  <circle cx="130" cy="50" r="2" fill="{C}" opacity="0.5"/>
  <circle cx="190" cy="70" r="2" fill="{P}" opacity="0.5"/>
  <circle cx="140" cy="85" r="1.5" fill="{C}" opacity="0.3"/>
''')


# ═════════════════════════════════════════════════════════
# 7. NETWORK MAP
# ═════════════════════════════════════════════════════════

def gen_network_map_bg():
    return svg(800, 400, f'''
  <rect width="800" height="400" fill="#0f172a" rx="8"/>
  <!-- Japan outline (simplified) -->
  <path d="M420 120 L430 100 L450 90 L460 100 L455 120 L460 140 L450 160 L440 180 L430 200 L420 220 L410 240 L400 260 L390 250 L385 230 L390 210 L400 190 L405 170 L410 150 L415 130Z" fill="{GR}" opacity="0.1"/>
  <!-- Nodes -->
  <circle cx="410" cy="150" r="5" fill="{G}"><animate attributeName="opacity" values="0.5;1;0.5" dur="2s" repeatCount="indefinite"/></circle>
  <circle cx="430" cy="180" r="4" fill="{G}"><animate attributeName="opacity" values="0.5;1;0.5" dur="2.3s" repeatCount="indefinite"/></circle>
  <circle cx="390" cy="200" r="4" fill="{C}"><animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" repeatCount="indefinite"/></circle>
  <circle cx="450" cy="130" r="3" fill="{P}"><animate attributeName="opacity" values="0.5;1;0.5" dur="2.5s" repeatCount="indefinite"/></circle>
  <circle cx="200" cy="200" r="3" fill="{B}" opacity="0.5"/>
  <circle cx="600" cy="150" r="3" fill="{B}" opacity="0.5"/>
  <!-- Lines -->
  <line x1="410" y1="150" x2="430" y2="180" stroke="{G}" stroke-width="0.5" opacity="0.3"/>
  <line x1="410" y1="150" x2="390" y2="200" stroke="{C}" stroke-width="0.5" opacity="0.3"/>
  <line x1="430" y1="180" x2="450" y2="130" stroke="{P}" stroke-width="0.5" opacity="0.3"/>
  <line x1="200" y1="200" x2="390" y2="200" stroke="{B}" stroke-width="0.5" opacity="0.15" stroke-dasharray="4"/>
  <line x1="450" y1="130" x2="600" y2="150" stroke="{B}" stroke-width="0.5" opacity="0.15" stroke-dasharray="4"/>
''')


# ═════════════════════════════════════════════════════════
# 8. STATUS & UI
# ═════════════════════════════════════════════════════════

def gen_status_online():
    return svg(12, 12, f'''
  <circle cx="6" cy="6" r="4" fill="{G}"/>
  <circle cx="6" cy="6" r="5.5" fill="{G}" opacity="0.2"/>
''')

def gen_status_offline():
    return svg(12, 12, f'<circle cx="6" cy="6" r="4" fill="{GR}" opacity="0.4"/>')

def gen_empty_state():
    return svg(200, 200, f'''
  <rect x="50" y="40" width="100" height="80" rx="8" stroke="{GR}" stroke-width="2" fill="none" opacity="0.3" stroke-dasharray="6"/>
  <line x1="80" y1="80" x2="120" y2="80" stroke="{GR}" stroke-width="1.5" opacity="0.2"/>
  <line x1="90" y1="90" x2="110" y2="90" stroke="{GR}" stroke-width="1.5" opacity="0.15"/>
  <text x="100" y="150" text-anchor="middle" font-family="system-ui" font-size="12" fill="{GR}" opacity="0.4">No Data</text>
''')

def gen_chat_icon():
    return svg(24, 24, f'''
  <path d="M4 18V6a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H8l-4 4z" stroke="url(#gp)" stroke-width="1.5" fill="none"/>
  <line x1="9" y1="9" x2="15" y2="9" stroke="url(#gp)" stroke-width="1" opacity="0.5"/>
  <line x1="9" y1="12" x2="13" y2="12" stroke="url(#gp)" stroke-width="1" opacity="0.5"/>
''')

def gen_score_trophy():
    return svg(48, 48, f'''
  <path d="M16 8h16v12c0 6-4 10-8 10s-8-4-8-10V8z" stroke="{GOLD}" stroke-width="2" fill="{GOLD}" fill-opacity="0.15"/>
  <path d="M16 12H10c0 4 2 7 6 8" stroke="{GOLD}" stroke-width="1.5" fill="none"/>
  <path d="M32 12H38c0 4-2 7-6 8" stroke="{GOLD}" stroke-width="1.5" fill="none"/>
  <line x1="20" y1="36" x2="28" y2="36" stroke="{GOLD}" stroke-width="2" stroke-linecap="round"/>
  <line x1="24" y1="30" x2="24" y2="36" stroke="{GOLD}" stroke-width="2"/>
''')

def gen_arrow_up():
    return svg(16, 16, f'''
  <path d="M8 12V4M4 7l4-4 4 4" stroke="{G}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
''')


# ═════════════════════════════════════════════════════════
# 9. CONNECTION ICONS
# ═════════════════════════════════════════════════════════

def gen_conn_ssh():
    return svg(20, 20, f'''
  <rect x="2" y="4" width="16" height="12" rx="2" stroke="{G}" stroke-width="1.5" fill="none"/>
  <text x="10" y="13" text-anchor="middle" font-family="monospace" font-size="6" font-weight="700" fill="{G}">$_</text>
''')

def gen_conn_tailscale():
    return svg(20, 20, f'''
  <circle cx="10" cy="6" r="2.5" fill="{P}" opacity="0.7"/>
  <circle cx="5" cy="14" r="2.5" fill="{P}" opacity="0.7"/>
  <circle cx="15" cy="14" r="2.5" fill="{P}" opacity="0.7"/>
  <line x1="10" y1="8.5" x2="5" y2="11.5" stroke="{P}" stroke-width="1" opacity="0.4"/>
  <line x1="10" y1="8.5" x2="15" y2="11.5" stroke="{P}" stroke-width="1" opacity="0.4"/>
  <line x1="5" y1="14" x2="15" y2="14" stroke="{P}" stroke-width="1" opacity="0.4"/>
''')

def gen_conn_wireguard():
    return svg(20, 20, f'''
  <path d="M10 3L3 8v6l7 4 7-4V8z" stroke="{Y}" stroke-width="1.5" fill="{Y}" fill-opacity="0.1"/>
  <path d="M10 8v5" stroke="{Y}" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="10" cy="15" r="1" fill="{Y}"/>
''')

def gen_conn_local():
    return svg(20, 20, f'''
  <path d="M3 10l7-6 7 6v7a1 1 0 01-1 1H4a1 1 0 01-1-1v-7z" stroke="{W}" stroke-width="1.5" fill="none" opacity="0.7"/>
  <rect x="8" y="13" width="4" height="5" stroke="{W}" stroke-width="1" fill="none" opacity="0.5"/>
''')


# ═════════════════════════════════════════════════════════
# PNG画像（Gemini生成）
# ═════════════════════════════════════════════════════════

PNG_IMAGES = {
    "hero-bg": {
        "filename": "hero-bg.png",
        "width": 1920, "height": 1080,
        "aspect_ratio": "16:9",
        "prompt": (
            "Dark background with neon glow network visualization. "
            "Purple, blue, and cyan glowing particles connected by thin light lines, "
            "forming a distributed network pattern. Space-like depth with gradient mesh. "
            "Colors: dark navy (#0f172a) base, purple (#8b5cf6), blue (#3b82f6), cyan (#06b6d4) glow. "
            "Web3/blockchain atmosphere. No text. No watermarks."
        ),
    },
    "og-image": {
        "filename": "og-image.png",
        "width": 1200, "height": 630,
        "aspect_ratio": "16:9",
        "prompt": (
            "Dark background (#0f172a) banner. Three glowing network nodes (purple-blue gradient circles) "
            "connected by light lines in the left portion. Right side has space for text overlay. "
            "Subtle glow effects. Web3 dashboard atmosphere. "
            "Purple (#8b5cf6) to blue (#3b82f6) color scheme. No text."
        ),
    },
}


def generate_png(key, spec, output_path):
    from PIL import Image as PILImage
    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        print("  ERROR: google-genai not installed")
        return False

    client = genai.Client(api_key=GEMINI_API_KEY)
    gen_config = gtypes.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=gtypes.ImageConfig(aspect_ratio=spec["aspect_ratio"]),
    )
    t0 = time.time()
    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=[spec["prompt"]], config=gen_config,
    )
    print(f"  {time.time()-t0:.1f}s", end="", flush=True)

    for part in response.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            raw = part.as_image()
            raw.save(str(output_path))
            # Resize
            img = PILImage.open(output_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            tw, th = spec["width"], spec["height"]
            tr = tw / th; ir = img.width / img.height
            if ir > tr:
                nh = th; nw = int(img.width * (th / img.height))
            else:
                nw = tw; nh = int(img.height * (tw / img.width))
            img = img.resize((nw, nh), PILImage.LANCZOS)
            l = (nw - tw) // 2; t = (nh - th) // 2
            img = img.crop((l, t, l + tw, t + th))
            img.save(str(output_path), "PNG", optimize=True)
            fsize = output_path.stat().st_size / 1024
            print(f" → {tw}x{th} {fsize:.0f}KB")
            img.close()
            return True

    print("  FAILED")
    return False


# ═════════════════════════════════════════════════════════
# メイン
# ═════════════════════════════════════════════════════════

SVG_REGISTRY = {
    # 1. Logo
    "logo": ("logo.svg", gen_logo),
    "logo-full": ("logo-full.svg", gen_logo_full),
    # 2. Top
    "wallet-icon": ("wallet-icon.svg", gen_wallet_icon),
    "network-illustration": ("network-illustration.svg", gen_network_illustration),
    # 3. My Page
    "avatar-default": ("avatar-default.svg", gen_avatar_default),
    "node-online": ("node-online.svg", gen_node_online),
    "node-offline": ("node-offline.svg", gen_node_offline),
    "pc-icon": ("pc-icon.svg", gen_pc_icon),
    "macmini-icon": ("macmini-icon.svg", gen_macmini_icon),
    # 4. Service
    "svc-x": ("svc-x.svg", gen_svc_x),
    "svc-instagram": ("svc-instagram.svg", gen_svc_instagram),
    "svc-tiktok": ("svc-tiktok.svg", gen_svc_tiktok),
    "svc-facebook": ("svc-facebook.svg", gen_svc_facebook),
    "svc-youtube": ("svc-youtube.svg", gen_svc_youtube),
    "svc-gmail": ("svc-gmail.svg", gen_svc_gmail),
    "svc-github": ("svc-github.svg", gen_svc_github),
    "svc-cloudflare": ("svc-cloudflare.svg", gen_svc_cloudflare),
    # 5. Task
    "task-site": ("task-site.svg", gen_task_site),
    "task-sns": ("task-sns.svg", gen_task_sns),
    "task-gmail": ("task-gmail.svg", gen_task_gmail),
    "task-git": ("task-git.svg", gen_task_git),
    "task-cloudflare": ("task-cloudflare.svg", gen_task_cloudflare),
    "task-automation": ("task-automation.svg", gen_task_automation),
    "task-api": ("task-api.svg", gen_task_api),
    "task-p2p": ("task-p2p.svg", gen_task_p2p),
    "task-storage": ("task-storage.svg", gen_task_storage),
    "task-review": ("task-review.svg", gen_task_review),
    # 6. CLT
    "clt-token": ("clt-token.svg", gen_clt_token),
    "clt-token-sm": ("clt-token-sm.svg", gen_clt_token_sm),
    "merkle-icon": ("merkle-icon.svg", gen_merkle_icon),
    "claim-illustration": ("claim-illustration.svg", gen_claim_illustration),
    # 7. Network
    "network-map-bg": ("network-map-bg.svg", gen_network_map_bg),
    # 8. Status & UI
    "status-online": ("status-online.svg", gen_status_online),
    "status-offline": ("status-offline.svg", gen_status_offline),
    "empty-state": ("empty-state.svg", gen_empty_state),
    "chat-icon": ("chat-icon.svg", gen_chat_icon),
    "score-trophy": ("score-trophy.svg", gen_score_trophy),
    "arrow-up": ("arrow-up.svg", gen_arrow_up),
    # 9. Connection
    "conn-ssh": ("conn-ssh.svg", gen_conn_ssh),
    "conn-tailscale": ("conn-tailscale.svg", gen_conn_tailscale),
    "conn-wireguard": ("conn-wireguard.svg", gen_conn_wireguard),
    "conn-local": ("conn-local.svg", gen_conn_local),
}


def main():
    parser = argparse.ArgumentParser(description="Node Dashboard Assets (~45 files)")
    parser.add_argument("--group", choices=["svg", "png", "all"], default="all")
    args = parser.parse_args()

    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    if args.group in ("svg", "all"):
        for key, (filename, gen_func) in SVG_REGISTRY.items():
            out = ICONS_DIR / filename
            content = gen_func()
            out.write_text(content)
            fsize = out.stat().st_size / 1024
            print(f"  OK {filename} ({fsize:.1f}KB)")
            results[key] = True

    if args.group in ("png", "all"):
        for key, spec in PNG_IMAGES.items():
            out = ICONS_DIR / spec["filename"]
            print(f"  [{key}] {spec['filename']}", end=" ", flush=True)
            results[key] = generate_png(key, spec, out)
            time.sleep(2)

    # favicon.ico (generate from logo SVG concept)
    if args.group in ("svg", "all"):
        # Simple favicon as PNG (browsers accept PNG favicons)
        from PIL import Image as PILImage, ImageDraw as PIDraw
        fav = PILImage.new("RGBA", (32, 32), (0, 0, 0, 0))
        d = PIDraw.Draw(fav)
        # Purple-blue gradient circle with N
        d.ellipse([2, 2, 30, 30], fill=(139, 92, 246, 255))
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
        except Exception:
            font = ImageFont.load_default()
        d.text((10, 5), "N", fill=(255, 255, 255, 255), font=font)
        fav_path = PUBLIC_DIR / "favicon.ico"
        fav.save(str(fav_path), "ICO")
        print(f"  OK favicon.ico ({fav_path.stat().st_size / 1024:.1f}KB)")
        results["favicon"] = True

    ok = sum(1 for v in results.values() if v)
    print(f"\n{'='*50}")
    print(f"Results: {ok}/{len(results)} succeeded")
    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    return all(results.values())


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

#!/usr/bin/env python3
"""Generate market-data.json for market.morm.one.

Aggregates, from public data only:
  - live price + pool reserves + TVL (Base pool slot0/balances)
  - price history + USDC volume (pool Swap events)
  - bridged-MORM history = wMORM total supply over time (WMORM mint/burn Transfers)
  - forward/exit/swap counts
  - L1 treasury balance (read from the local L1 node)

Incremental: reads its own previous output for cursor + history, scans only new
blocks, appends. getLogs is recursively split on any provider range/size error
(works on free-tier RPCs). Run on ts-mini via cron; nginx serves the JSON.
"""
import json, os, time, urllib.request

RPC = os.environ.get("BASE_RPC", "https://mainnet.base.org")   # server-side; chunked so no 413
L1  = os.environ.get("MORM_RPC", "http://127.0.0.1:8900")
OUT = os.environ.get("MARKET_DATA_OUT", "/Users/user/zoku-sites/morm-market/market-data.json")
POOL  = "0x6615fC0239eDDb27A8fF2D774C438e68C4599A55".lower()
WMORM = "0x7fEf327a811e73F06cccF0De9db022e739d5076d".lower()
USDC  = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".lower()
START = 50605354            # wMORM/bridge deploy block (covers all mints since inception)
TREASURY = "m0rzjtzf3okk3zu2pgyuzdhpnp2asbgctbc"
SWAP     = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO = "0x" + "0" * 64
MAXHIST = 3000

MAX_RANGE = int(os.environ.get("MAX_RANGE", "800"))   # getLogs 初期チャンク幅（Alchemy無料枠なら10に）
_id = [0]
def rpc(url, method, params):
    _id[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _id[0], "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "content-type": "application/json",
        "user-agent": "curl/8.4.0"})       # 公開RPCは python-urllib 既定UAを403で弾くため
    j = json.loads(urllib.request.urlopen(req, timeout=25).read())
    if j.get("error"):
        raise Exception(j["error"])
    return j["result"]

def base(m, p): return rpc(RPC, m, p)
def hexn(h): return int(h, 16)
def hx(n):  return hex(n)
def word(data, i):
    s = data[2:]
    return int(s[i * 64:(i + 1) * 64] or "0", 16)
def signed(u): return u - (1 << 256) if u >= (1 << 255) else u
def price_from_sqrt(sqrt_int):
    r = sqrt_int / (2 ** 96)
    return r * r * 1e12          # wMORM(18)=token0, USDC(6)=token1 → USDC per wMORM

def _logs_split(addr, topics, frm, to):
    """getLogs with recursive range-splitting on any provider range/size error."""
    try:
        return base("eth_getLogs", [{"address": addr, "topics": topics,
                                     "fromBlock": hx(frm), "toBlock": hx(to)}])
    except Exception:
        if to <= frm:
            return []
        mid = (frm + to) // 2
        return _logs_split(addr, topics, frm, mid) + _logs_split(addr, topics, mid + 1, to)

def get_logs(addr, topics, frm, to):
    """Scan [frm,to] in MAX_RANGE-sized windows (split further on error)."""
    out = []
    f = frm
    while f <= to:
        t = min(f + MAX_RANGE - 1, to)
        out += _logs_split(addr, topics, f, t)
        f = t + 1
    return out

def block_times(blocks):
    m = {}
    for b in set(blocks):
        bl = base("eth_getBlockByNumber", [hx(b), False])
        m[b] = hexn(bl["timestamp"])
    return m

# ---- load previous output as state ----
st = {}
try:
    st = json.load(open(OUT))
except Exception:
    pass
priceHist   = st.get("priceHistory", [])
bridgedHist = st.get("bridgedHistory", [])
counts      = st.get("counts", {"forwards": 0, "exits": 0, "swaps": 0})
last        = st.get("lastBlock", START - 1)
bridged_wei = st.get("_bridgedWei", 0)

head = hexn(base("eth_blockNumber", []))
if head > last:
    swaps = get_logs(POOL,  [[SWAP]],     last + 1, head)
    tw    = get_logs(WMORM, [[TRANSFER]], last + 1, head)
    blks  = [hexn(l["blockNumber"]) for l in swaps] + [hexn(l["blockNumber"]) for l in tw]
    tmap  = block_times(blks) if blks else {}
    for l in swaps:
        blk = hexn(l["blockNumber"])
        priceHist.append({"t": tmap[blk] * 1000,
                          "p": price_from_sqrt(word(l["data"], 2)),
                          "v": abs(signed(word(l["data"], 1))) / 1e6})
        counts["swaps"] += 1
    for l in sorted(tw, key=lambda x: (hexn(x["blockNumber"]), hexn(x["logIndex"]))):
        val = word(l["data"], 0)
        if l["topics"][1] == ZERO:      # mint (bridge forward)
            bridged_wei += val; counts["forwards"] += 1
        elif l["topics"][2] == ZERO:    # burn (exit)
            bridged_wei -= val; counts["exits"] += 1
        else:
            continue
        blk = hexn(l["blockNumber"])
        bridgedHist.append({"t": tmap[blk] * 1000, "wmorm": bridged_wei / 1e18})
    last = head

priceHist   = priceHist[-MAXHIST:]
bridgedHist = bridgedHist[-MAXHIST:]

# ---- current snapshot ----
slot0 = base("eth_call", [{"to": POOL, "data": "0x3850c7bd"}, "latest"])
price = price_from_sqrt(int(slot0[2:66], 16))
rw = int(base("eth_call", [{"to": WMORM, "data": "0x70a08231000000000000000000000000" + POOL[2:]}, "latest"]), 16) / 1e18
ru = int(base("eth_call", [{"to": USDC,  "data": "0x70a08231000000000000000000000000" + POOL[2:]}, "latest"]), 16) / 1e6
supply = int(base("eth_call", [{"to": WMORM, "data": "0x18160ddd"}, "latest"]), 16) / 1e18   # totalSupply()
try:
    treasury = json.loads(urllib.request.urlopen(L1 + "/account/" + TREASURY, timeout=8).read())["balance"]
except Exception:
    treasury = None

out = {
    "updated": int(time.time()),
    "price": price,
    "reserves": {"wmorm": rw, "usdc": ru},
    "tvl": ru + rw * price,
    "bridged": supply,                 # wMORM total supply = MORM currently on Base
    "l1": {"treasury": treasury},      # MORM held by the L1 treasury (native)
    "counts": counts,
    "priceHistory": priceHist,
    "bridgedHistory": bridgedHist,
    "lastBlock": last,
    "_bridgedWei": bridged_wei,
}
tmp = OUT + ".tmp"
json.dump(out, open(tmp, "w"))
os.replace(tmp, OUT)
print("wrote", OUT, "| price", round(price, 6), "| bridged", round(supply, 2),
      "| swaps", counts["swaps"], "| fwd", counts["forwards"], "| exit", counts["exits"])

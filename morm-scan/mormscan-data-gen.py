#!/usr/bin/env python3
"""Generate mormscan-data.json for scan.morm.one (MORMSCAN block explorer).

Public data only, no node modification (reads the L1 node's read-only RPC on
:8900 and Base's public RPC). Same static-site + generator pattern as
market-data-gen.py. Run on ts-mini via cron; nginx serves the JSON.

Produces:
  - chain overview (height, finalized, tips, mempool, producer, treasury)
  - recent blocks (height, hash, producer, tx count, ts)
  - recent transactions (flattened from recent blocks; kind decoded, sender m0r)
  - bridge tracer (cross-chain lifecycle):
      L1-initiated  from /bridge/burns (MORM→wMORM forward, USDm→Base) + status
      Base-initiated from Base logs (wMORM Exit, USDm Locked) → heading to MORM
  - Base snapshot (wMORM circulating supply, USDm escrow)
"""
import json, os, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "morm-l1"))
try:
    from morm_l1 import crypto            # address / bytes20 helpers (present on the node host)
except Exception:
    crypto = None

L1   = os.environ.get("MORM_RPC", "http://127.0.0.1:8900")
RPC  = os.environ.get("BASE_RPC", "https://mainnet.base.org")
OUT  = os.environ.get("SCAN_DATA_OUT", "/Users/user/zoku-sites/morm-scan/mormscan-data.json")
NBLK = int(os.environ.get("SCAN_BLOCKS", "60"))     # recent blocks to detail
NTX  = int(os.environ.get("SCAN_TXS", "120"))       # recent txs to keep
NBR  = int(os.environ.get("SCAN_BRIDGES", "120"))   # recent bridge flows to keep

WMORM      = "0x7fEf327a811e73F06cccF0De9db022e739d5076d"
USDC       = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BRIDGE     = "0x08Adb8d2c67491249C20edE2A7460d9f4Bd3907A"   # wMORM export bridge
USDM       = "0xd65896532806030878DB852F3f5216Bc917FD376"
USDMBRIDGE = "0x87cD170BA7a82a0049F2fF36aa926033A5f9C26e"
START      = int(os.environ.get("SCAN_START", "50605354"))  # bridge deploy block
MAX_RANGE  = int(os.environ.get("MAX_RANGE", "800"))

# Base event topic0 (see event sigs in the bridge ABIs)
T_EXIT   = "0xd4714aeeeeb8ed1c2c857c458ff680377b483e190610500444233086bf651f16"  # wMORM Exit(uint256,address,bytes20,uint256)
T_LOCKED = "0x8c62004188ea6a98ed43aca4d9b06573e53b52f46702640c14df70aaa5222968"  # USDm  Locked(uint256,address,bytes20,uint256)

KIND = {1:"REGISTER_CONTENT",2:"CREATE_ORDER",3:"SUBMIT_PROOF",4:"FINALIZE",5:"STAKE",
        6:"TRANSFER",7:"VIEW_REWARD",10:"POST_JOB",11:"CLAIM_JOB",12:"SUBMIT_WORK_PROOF",
        20:"BRIDGE_MINT",21:"BRIDGE_BURN",30:"REGISTER_AI_SERVICE",31:"REGISTER_PRODUCER",
        32:"REGISTER_TREASURY_SIGNERS",33:"MULTISIG_TX"}

_id = [0]
def rpc(url, method, params):
    _id[0] += 1
    body = json.dumps({"jsonrpc":"2.0","id":_id[0],"method":method,"params":params}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "content-type":"application/json","user-agent":"curl/8.4.0"})
    j = json.loads(urllib.request.urlopen(req, timeout=25).read())
    if j.get("error"): raise Exception(j["error"])
    return j["result"]

def base(m,p): return rpc(RPC,m,p)
def getj(path): return json.loads(urllib.request.urlopen(L1+path, timeout=10).read())
def hexn(h): return int(h,16)
def hx(n):  return hex(n)

def addr(pub_hex):
    if crypto:
        try: return crypto.address(bytes.fromhex(pub_hex))
        except Exception: pass
    return pub_hex[:12]+"…"

def m0r_from_topic(topic):
    # indexed bytes20 → left-aligned in the 32-byte topic: first 20 bytes
    b20 = bytes.fromhex(topic[2:][:40])
    if crypto:
        try: return crypto.bytes20_to_address(b20)
        except Exception: pass
    return "0x"+b20.hex()

def _logs_split(addr_, topics, frm, to):
    try:
        return base("eth_getLogs", [{"address":addr_,"topics":topics,
                                     "fromBlock":hx(frm),"toBlock":hx(to)}])
    except Exception:
        if to<=frm: return []
        mid=(frm+to)//2
        return _logs_split(addr_,topics,frm,mid)+_logs_split(addr_,topics,mid+1,to)

def get_logs(addr_, topics, frm, to):
    out=[]; f=frm
    while f<=to:
        t=min(f+MAX_RANGE-1,to)
        out+=_logs_split(addr_,topics,f,t); f=t+1
    return out

def call(to, data, dec):
    return int(base("eth_call",[{"to":to,"data":data},"latest"]),16)/dec

def tx_summary(kind, p):
    p = p or {}
    if kind==6:  return {"amount":p.get("amount"),"to":p.get("to"),"token":"MORM"}
    if kind==21: return {"amount":p.get("amount"),"to":p.get("evm_recipient"),"token":p.get("token","MORM")}
    if kind==20: return {"amount":p.get("amount"),"to":p.get("to"),"token":p.get("token","MORM")}
    if kind==5:  return {"amount":p.get("amount"),"token":"MORM"}
    if kind==33: return {"inner":KIND.get(int(p.get("inner_kind",0)),str(p.get("inner_kind")))}
    return {}

# ── load previous output for Base cursor + bridge history ──
st = {}
try: st = json.load(open(OUT))
except Exception: pass
base_flows = st.get("_baseFlows", [])
last_base  = st.get("_lastBaseBlock", START-1)

# ── L1: chain + blocks + txs ──
info = getj("/info")
treasury_addr = info.get("treasury") or "m0rzjtzf3okk3zu2pgyuzdhpnp2asbgctbc"   # /info.treasury = address
try: treasury_bal = getj("/account/"+treasury_addr).get("balance")
except Exception: treasury_bal = None
latest = getj(f"/blocks/latest?n={NBLK}").get("blocks", [])
blocks=[]; txs=[]
for b in latest:
    h = b.get("hash")
    try: full = getj(f"/block/{h}")
    except Exception: full=None
    trs = (full or {}).get("transactions", []) if full else []
    ts  = (full or {}).get("header",{}).get("timestamp", 0)
    blocks.append({"height":b.get("height"),"hash":h,
                   "producer":addr(b.get("producer","")),"txs":len(trs),"ts":ts})
    for t in trs:
        k=int(t.get("kind",0))
        txs.append({"hash":(full.get("hash") if full else h),
                    "kind":k,"kindName":KIND.get(k,str(k)),
                    "sender":addr(t.get("sender","")),"nonce":t.get("nonce"),
                    "height":b.get("height"),"ts":ts, **tx_summary(k,t.get("payload"))})
txs = sorted(txs,key=lambda x:(x["height"] or 0),reverse=True)[:NTX]

# ── bridge tracer: L1-initiated (from /bridge/burns) ──
bridges=[]
try:
    for br in getj("/bridge/burns").get("burns", []):
        tok=br.get("token") or "MORM"
        bridges.append({
            "dir":"MORM→Base","asset":("MORM→wMORM" if tok=="MORM" else tok),
            "token":tok,"l1Tx":br.get("burn_tx_hash"),"from":br.get("burner"),
            "amount":br.get("amount"),"to":br.get("evm_recipient"),
            "status":"confirmed" if br.get("evm_unlocked") else "pending",
            "ts":br.get("burned_at",0)})
except Exception as e:
    print("[scan] bridge/burns failed:", e)

# ── bridge tracer: Base-initiated (Base logs; best-effort, incremental) ──
try:
    head = hexn(base("eth_blockNumber",[]))
    if head>last_base:
        ex  = get_logs(BRIDGE, [[T_EXIT]],   last_base+1, head)
        lk  = get_logs(USDMBRIDGE, [[T_LOCKED]], last_base+1, head)
        need=set(hexn(l["blockNumber"]) for l in ex+lk)
        tmap={b:hexn(base("eth_getBlockByNumber",[hx(b),False])["timestamp"])*1000 for b in need}
        for l in ex:
            bn=hexn(l["blockNumber"])
            base_flows.append({"dir":"Base→MORM","asset":"wMORM→MORM","token":"MORM",
                "baseTx":l["transactionHash"],"from":"0x"+l["topics"][2][-40:],
                "amount":str(hexn(l["data"][2:66])),"to":m0r_from_topic(l["topics"][3]),
                "status":"onbase","ts":tmap.get(bn,0)})
        for l in lk:
            bn=hexn(l["blockNumber"])
            base_flows.append({"dir":"Base→MORM","asset":"USDm","token":"USDm",
                "baseTx":l["transactionHash"],"from":"0x"+l["topics"][2][-40:],
                "amount":str(hexn(l["data"][2:66])),"to":m0r_from_topic(l["topics"][3]),
                "status":"onbase","ts":tmap.get(bn,0)})
        last_base=head
    base_flows=base_flows[-NBR:]
    bridges += base_flows
except Exception as e:
    print("[scan] base logs failed:", e)

bridges = sorted(bridges,key=lambda x:(x.get("ts") or 0),reverse=True)[:NBR]

# ── Base snapshot ──
snap={}
try:
    snap["bridged_wmorm"]=call(WMORM,"0x18160ddd",1e18)                                   # totalSupply
    snap["usdm_escrow"]=call(USDM,"0x70a08231000000000000000000000000"+USDMBRIDGE[2:],1e6) # balanceOf(bridge)
    snap["usdm_supply"]=call(USDM,"0x18160ddd",1e6)
except Exception as e:
    print("[scan] base snapshot failed:", e)

out={
  "updated":int(time.time()),
  "chain":{"height":info.get("head_height") or (latest[0]["height"] if latest else 0),
           "finalized":info.get("finalized_height"),"tips":len(info.get("tips",[])),
           "mempool":info.get("mempool"),"producer":info.get("producer_address"),
           "treasury_addr":treasury_addr,"treasury":treasury_bal,
           "state_root":info.get("state_root")},
  "base":{**snap,"wmorm":WMORM,"usdm":USDM,"bridge":BRIDGE,"usdmbridge":USDMBRIDGE},
  "blocks":blocks,"txs":txs,"bridges":bridges,
  "_baseFlows":base_flows,"_lastBaseBlock":last_base,
}
tmp=OUT+".tmp"; json.dump(out,open(tmp,"w")); os.replace(tmp,OUT)
print("wrote",OUT,"| height",out["chain"]["height"],"| blocks",len(blocks),
      "| txs",len(txs),"| bridges",len(bridges))

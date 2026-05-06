# MORM for Node Operators — Landing Page Copy

Target: home PC / GPU-server owners, data-center operators, always-on Mac mini users, gamers, Web3 DePIN investors

---

## Hero

> ## **Put your idle machine to work.**
>
> GPU. SSD. Bandwidth. Uptime.
> Spare resources turn into MORM Token, every day.
>
> [Set up a node (5 minutes)]

---

## Market Size

```
Your home RTX 4090 running 24h ≈ 1,500–6,000 MORM/month
Net positive even after electricity costs
```

The DePIN market is at $3.2B and growing rapidly. MORM is the most anticipated integrated stack within the video + AI segment.

---

## Why MORM Nodes

### Compared to existing DePIN

| Project | Resource | Reward Weight | MORM Difference |
|---|---|---|---|
| Filecoin | Storage | High | MORM stacks video + AI rewards |
| Theta | Bandwidth | Medium | MORM rewards encoding + verification too |
| Render | GPU (3D) | High | MORM is video-specific, demand is steadier |
| Livepeer | GPU (transcoding) | High | MORM also integrates AI |
| Akash | General compute | Medium | MORM's specialized jobs run more efficiently |
| **MORM** | **GPU / Bandwidth / SSD / Uptime** | **Multi-stacked maximum** | **Unified video + AI + delivery + verification** |

MORM is designed so that **one machine earns from four kinds of work** simultaneously, maximizing utilization.

---

## Rewards by Resource

| Resource | Work | Weight |
|---|---|---|
| **GPU Power** | Video encoding, AI analysis, frame generation, verification | **Highest** |
| **Bandwidth** | P2P video delivery, caching for Light Clients | **High** |
| **SSD Storage** | MORM Cells retention (popular content earns more) | **Medium** |
| **Active Time** | Uptime, stability, latency | **Low** |

### Monthly Earnings Simulation (tentative)

| Setup | Monthly reward (estimate) |
|---|---|
| 1 × RTX 4090 24h | 1,500–6,000 MORM |
| 1 × RTX 6000 BW 24h | 5,000–20,000 MORM |
| Mac mini M2 24h (bandwidth + SSD) | 200–800 MORM |
| Gaming PC idle hours only | 100–500 MORM |
| Phone while charging only (Light Client) | 5–30 MORM |

> ※ Tentative. Actual rewards depend on network maturity and participant count.

---

## Setup

### Requirements

- Internet (≥20 Mbps upload)
- OS: Linux, macOS, Windows, Docker
- Optional: GPU (NVIDIA / AMD / Apple Silicon), SSD space

### Step 1: Download node software

```
# Phase 30 (current — Docker compose installer):
curl -fsSL https://raw.githubusercontent.com/Kemonos0424/morm/main/docker/install.sh | bash

# Future (planned — once an authoritative DNS zone is acquired):
# curl -fsSL https://get.<acquired-zone>/morm | sh
```

Note: `get.morm.network` is **not** currently registered by this project.
Until an authoritative zone is acquired, all install paths route through
the GitHub raw URL above (verifiable against the public source repo). Be
suspicious of any other "official" install URL.

Future package-manager paths (planned, not yet shipped):

- macOS: `brew install morm-node`
- Windows: official MSI installer
- Linux: `apt install morm-node` / `yum install morm-node`

### Step 2: First launch and authentication

```
morm-node init
```

Authenticate via biometrics on phone → device registers on MORM Chain → node starts.

### Step 3: Choose what to provide

```
morm-node configure
  --gpu enable
  --bandwidth-cap 100mbps
  --storage-cap 100GB
  --active-hours 24
```

### Step 4: Monitor rewards

Dashboard (Web, CLI, mobile) shows real-time:
- Resources contributed
- PoUW work completed
- Cumulative MORM rewards
- Staking status

---

## Hardware Optimization Guides

### RTX 6000 Ada / RTX 6000 BW

Top-tier setup. Runs AI analysis + transcoding + delivery in parallel.

- Recommended: Linux, 24/7
- Monthly estimate: 8,000–25,000 MORM
- Power draw: ~300W (~$30–80/month depending on region)

### RTX 4090 / 5090

High-end gaming PC. Can run only on idle hours.

- Recommended: Windows / Linux
- Monthly estimate: 1,500–6,000 MORM
- Auto-pause during gaming sessions supported

### Apple Silicon (Mac mini M2/M3/M4)

Low power, high efficiency. Specialized in video encoding (VideoToolbox).

- Recommended: macOS, fanless 24/7
- Monthly estimate: 500–2,000 MORM
- Power draw: ~30W

### Raspberry Pi cluster

Storage + bandwidth-only node. Low capex, deploy at scale.

- Recommended: Linux ARM
- Monthly estimate: 50–200 MORM / unit
- Future: dedicated MORM Hardware nodes

---

## NodePower vs Edge Node

| Type | Requirements | Monthly estimate |
|---|---|---|
| **Validator (NodePower)** | High-end GPU + 24h uptime + stable network | 5,000–25,000 MORM |
| **Edge Node** | SSD + bandwidth + stable uptime | 500–3,000 MORM |
| **Light Client** | Phone or PC only | 5–100 MORM |

Recommended path: start as Light Client → upgrade to Edge Node → eventually NodePower.

---

## The Role of Staking (Bonding)

Running a node requires a minimum bond per Tier:

| Tier | Min stake |
|---|---|
| Light Client | 0 MORM |
| Edge Node | 100 MORM |
| Validator | 10,000 MORM |
| Validator (Publisher Tier) | 100,000 MORM |

Larger stakes = higher work-allocation priority. **Slashing for malicious behavior is enforced — honest operation is required.**

---

## Risks & Safeguards

| Risk | MORM countermeasure |
|---|---|
| Spoofed nodes (false resource reporting) | Challenge-response verification, slashable |
| Sybil attacks | Biometric-based ID, permanent ban |
| 51% attacks | PoUW useful-work requirement, Validator diversity |
| Hardware failure | Grace period, restart penalty waived |
| Network outage | Temporary reward reduction, full recovery on rejoin |

**As long as you operate honestly, slashing risk is near zero.**

---

## Long-term Earnings Outlook

### MORM Phase 0 (0–6 mo)

- Few competitors, max APY (~18-25% effective)
- Strong node-uptime bonus (1.5×)
- Risks: immature network, token-price volatility

### MORM Phase 1 (6–18 mo)

- More nodes, APY 12-18%
- Stable workload
- Benefits from network growth

### MORM Phase 2 (18–36 mo)

- Public launch demand surge
- APY 8-12% (mature)
- Stake-value upside

### MORM Phase 3 (36+ mo)

- 10M-node scale
- APY 5-8% (steady)
- DAO participation rewards

---

## Operator Community

- **Discord**: setup support, optimization tips
- **GitHub**: open-source code, issue tracker
- **Monthly AMA**: direct dialogue with core dev team
- **Hardware Working Group**: dedicated devices, ASIC discussion

Node operators aren't just yield-takers — they are **co-owners** of the MORM network.

---

## FAQ (for Node Operators)

### Q. How much initial investment do I need?

A. Zero is fine. Your existing phone / PC works as a Light Client. To go bigger, gaming PCs ($1,000–2,000) or dedicated GPU servers ($10,000+) are options.

### Q. Will electricity costs make this profitable?

A. Depends on region and hardware. In the US/EU at $0.20/kWh, an RTX 4090 24/7 costs ~$45/month. With monthly rewards estimated at 1,500–6,000 MORM (which at current rates equals $300–1200), this is net positive. We will provide an earnings simulator that factors in market price and local power costs.

### Q. Can I run multiple nodes on one account?

A. Yes. One MORM ID can be linked to multiple devices. To prevent Sybil attacks, each device requires biometrics or hardware binding.

### Q. Can I run at data-center scale?

A. Yes. From MORM Phase 1 onward, an "Operator License" for data-center operators will be available. With corporate KYC, you can run 1000+ nodes.

### Q. Does it work on AMD or Apple Silicon?

A. Yes. MORM AI / encoding supports ROCm (AMD), VideoToolbox (Apple Silicon). NVIDIA's CUDA stack is currently the most efficient.

---

## Invite Program

MORM Phase 0 node operators get:

- Maximum APY boost (1.5× early multiplier)
- MORM Initial Airdrop priority
- Early Pioneer-Tier eligibility (with DAO weight)

[Apply to Operate]

---

## Closing

> Servers used to be: someone buys them, someone racks them, someone operates them.
> MORM is different. You rack it. You operate it. You earn from it.
>
> Centralized infrastructure no longer needs you.
> But MORM does.
>
> **The Swarm for Every Frame.**
>
> [Start Your Node]

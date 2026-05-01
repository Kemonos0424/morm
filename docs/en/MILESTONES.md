# MORM Milestones (Detailed)

**Version**: 0.3 (Draft)
**Date**: 2026-04-25
**Status**: Internal planning / progress tracking

---

## Implementation Status (as of 2026-04-26)

**PoC Phase 1-27f all implemented and verified on real hardware (46 items).**
**SECURITY-DESIGN §5 must-have all met = mainnet candidate minimum requirements OK.**

See `docs/IMPLEMENTATION-STATUS.md` for full detail. Key milestones:

- ✅ 3-second WebM Cells + V-Hash (PoC Phase 1/2)
- ✅ Walletless ID (PoC Phase 7/9/11b)
- ✅ Proof of Physical Evidence (PoC Phase 5/10e/16)
- ✅ Smart Contracts (32/32 Forge tests PASS in total)
- ✅ MORM L1 Testnet (PoC Phase 10a-c + 23 3-node testnet)
- ✅ 50/10 Player + P2P Mesh (PoC Phase 3/6)
- ✅ WebRTC P2P + TURN (PoC Phase 22/22b, coturn operational)
- ✅ Player↔Chain on-chain view rewards (PoC Phase 11d)
- ✅ Unified CLI `morm` (PoC Phase 22/23)
- ✅ EVM Bridge + ERC-20 + Multi-sig relayer (PoC Phase 12/13a/13b)
- ✅ AI Service Generation ID (PoC Phase 14)
- ✅ MORM Shop UX + Shamir + real-camera evidence (PoC Phase 15a/15b/16a)
- ✅ Multi-producer Slot + K-depth Finality + m0r-prefix (PoC Phase 17/17b/18)
- ✅ Node-invite UI + testnet ops + PWA (PoC Phase 19/20/21)
- ✅ **True DAG parallelism** (PoC Phase 24a-d, frontier-relative state, common-ancestor finality witness ≥⅔)
- ✅ **QUIC stream gossip** (PoC Phase 25a-c, aioquic 1.3, SPKI pin TOFU, HTTP `/gossip/*` 410'd)
- ✅ **Treasury Multi-sig** (PoC Phase 26a, M-of-N)
- ✅ **Web hardening** (PoC Phase 26u/v/w/x, CSRF/CORS/`MORM_PRODUCTION=1`/key-file mode 0600)
- ✅ **Tx confirm dialog** (PoC Phase 27f, shop.js + auth-morm.js wired)

**Remaining (sequential, recommended pre-mainnet)**:
- §🟡 Mempool size cap (26c), Genesis lockdown (26e), Slither/Echidna audit (26f), Cell SHA256 verify (26q), Signaling rate limit (26r/s), TURN bandwidth quota (26t), SW max-age (26y), DNSSEC + .morm TLD (27c)
- Phase 25-Video (native HLS), Phase 24b throughput optimization, Phase 26a-rotation

What remains is the **strategy, brand, community layer**:
- Domain / ENS acquisition (morm.io, morm.eth, etc.)
- Core contributor recruitment (pseudonymous OK)
- Whitepaper final publication
- AI Agents in production
- Founding Contributor (YACHIDA) public attribution

These are addressed under "2. Pre-Launch Phase" below.

---

## 0. Overall Map

```
2026  ───────────────────────────────────────────────────────
  Q2  | Pre-Launch       | AI Agent design, smart contract drafts, contributors
  Q3  | MORM Phase 0 α  | Testnet open, AI Agent infrastructure deploy
  Q4  | MORM Phase 0 β  | Public Testnet, third-party audits, MORM Shop α
2027  ───────────────────────────────────────────────────────
  Q1  | TGE & Phase 1 begins | Mainnet, MORM Initial Airdrop, DAO migration
  Q2  | Phase 1 accelerate    | iOS/Android v1, Verified Creators expand
  Q3  | Phase 1 expand        | MORM Studio, AI Lab, SEA rollout
  Q4  | Phase 1 complete      | 1M MAU, AI Agents fully operational
2028  ───────────────────────────────────────────────────────
  Q1-Q4 | MORM Phase 2 (Public) | App stores, SDK, Bridges, global
2029  ───────────────────────────────────────────────────────
  Q1-Q4 | MORM Phase 3 (Sovereign) | B2B, Spatial Video, fully autonomous
2030+ ───────────────────────────────────────────────────────
       | Maturity | 100M+ MAU, founding contributors fade to participants
```

> ⚠️ MORM has **no legal entity**. All operations run on AI Agents + Smart Contracts + DAO. See [AGENTS.md](AGENTS.md).

---

## 1. Phase-Transition Decision Gates

To advance between Phases, all required conditions must be met.

### Gate A: Pre-Launch → MORM Phase 0 α (target: 2026 Q3)

- [ ] Whitepaper v1.0 published (via GitHub)
- [ ] AI Agent design ([AGENTS.md](AGENTS.md)) public
- [ ] Internal audit of initial smart contracts
- [ ] 3 PoCs done (3-second Cells / Walletless ID / PoPE basics)
- [ ] 15+ core contributors (pseudonymous OK)
- [ ] Initial Treasury Multi-sig 5/7 signers selected
- [ ] Bug Bounty Contract ready to deploy

### Gate B: MORM Phase 0 → Phase 1 (TGE prep)

- [ ] Third-party smart contract audits (≥2 firms) passed
- [ ] 1,000 testnet validators stable
- [ ] Discord 50,000 members
- [ ] MORM Initial Airdrop whitelist finalized
- [ ] DEX liquidity bootstrap ready
- [ ] AI Agents (5+ types) production candidates verified
- [ ] Bug Bounty: 0 critical issues for 30 consecutive days
- [ ] Admin keys fully renounced (except Bridge / Multi-sig)

### Gate C: MORM Phase 1 → Phase 2 (Public Launch prep)

- [ ] MAU 1M achieved
- [ ] 100,000 active nodes
- [ ] Fraud rate <0.05%
- [ ] DAO self-governance operational (90 consecutive days, 24+ resolutions passed)
- [ ] Full AI Agent catalog (10+ types) operational
- [ ] Major-jurisdiction opt-out infrastructure complete
- [ ] PWA / app store dual distribution
- [ ] Localization in 5+ languages (via Translation Agent)

### Gate D: MORM Phase 2 → Phase 3

- [ ] MAU 10M achieved
- [ ] 1M active nodes
- [ ] 100+ DAO major resolutions executed
- [ ] Bridge cumulative volume $1B+
- [ ] Founding contributors hold zero special privileges (Multi-sig signers rotated)

---

## 2. Pre-Launch Phase (2026/04 – 2026/09)

**Goal**: AI Agent design, smart contract drafting, core contributors, PoCs.
**Note**: **No legal entity setup.** No employment contracts. Everything via Smart Contract Bounty.

### April 2026 (current month)

| Item | Detail | Track |
|---|---|---|
| ☐ Domain acquisitions | morm.network, morm.io, $MORM SNS handles, ENS `morm.eth` | Brand |
| ☐ Official X / Discord launch | Pseudonymous core contributors lead | Community |
| ☐ Whitepaper v0.2 review (this doc) | Community + early advisor review | Strategy |
| ☐ 15 core contributors gathered (pseudonymous OK) | Referral + crypto Twitter | Recruit |
| ☐ AGENTS.md published (AI Agent design) | Via GitHub | Tech |

**Month-end KPI**: 5 contributors, Discord 500, X 1K followers

### May 2026

| Item | Detail |
|---|---|
| ☐ AI Agent design detailed (5 core types) | Moderation / Treasury / Support / Analytics / Education |
| ☐ Brand kit completed | Logo, color, font, UI library |
| ☐ Whitepaper v1.0 published | Official site + GitHub + IPFS |
| ☐ Initial site live (Manifesto, Whitepaper, Roadmap) | morm.network |
| ☐ PoC #1: 3-second Cells streaming | Local env, 5 devices |
| ☐ Mailing list / Phase 0 Waitlist | Privy / Loops |

**KPI**: Discord 2K, Whitepaper DL 5K, Waitlist 10K

### June 2026

| Item | Detail |
|---|---|
| ☐ PoC #2: Walletless ID (Passkey + Social Recovery) | iOS/macOS/Windows |
| ☐ PoC #3: Proof of Physical Evidence prototype | Single video hash anchored |
| ☐ AI Agent prototype operations check | Moderation Agent α |
| ☐ Smart Contract v1 (Token / Distributor / Bounty / DAO Voting) | Internal review |
| ☐ Initial 10–15 Validator candidates selected | Community core contributors |
| ☐ 15 core contributors active | Protocol, AI, FE, DevOps |

**KPI**: Contributors 15, Discord 5K, Waitlist 30K

### July 2026

| Item | Detail |
|---|---|
| ☐ MORM Chain Testnet α code freeze | DAG consensus + PoUW prototype |
| ☐ Smart Contracts v1 complete | Escrow, Slash, distribution, DAO voting |
| ☐ Treasury Multi-sig 5/7 signers finalized | Geo-distributed, community-elected |
| ☐ AI Agents α release | GitHub, AGPL-3.0 |
| ☐ Initial Validator tech docs | GitHub public |
| ☐ First AMA (X Spaces / Discord) | Direct community dialogue |

**KPI**: Contributors 20, Discord 10K, X 25K

### August 2026

| Item | Detail |
|---|---|
| ☐ Testnet α internal launch | 5–10 internal Validators |
| ☐ AI Agents (5 types) coordinate on Testnet | Mod/Treasury/Support/Analytics/Edu |
| ☐ MORM Cells encode→deliver→verify PoC complete | Full pipeline on RTX 6000 BW |
| ☐ Bug Bounty Program live | Smart Contract Bounty + Immunefi |
| ☐ Audit firms contracted (OpenZeppelin, Trail of Bits) | ≥2 in parallel, via Audit Coordinator Agent |

**KPI**: Discord 25K, Waitlist 100K, test Validators 10

### September 2026 (Gate A)

| Item | Detail |
|---|---|
| ☐ Public Testnet (invite-only) opens | Target 100 Validators |
| ☐ Walletless ID β release | iOS/Android dedicated app |
| ☐ MORM Phase 0 α official announcement | Press release, X post |
| ☐ Gate A criteria check | Progress review |

**KPI**: Contributors 25, Discord 50K, Validators 100

---

## 3. MORM Phase 0 α/β (2026/10 – 2027/03)

**Goal**: Stabilize Testnet, complete audits, prepare TGE.
**Note**: AI Agents simulate production operations; smart contracts are finalized.

### October 2026

| Item | Detail |
|---|---|
| ☐ Public Testnet opens (target 500 Validators) | Gradually lower invite barrier |
| ☐ MORM Shop α closed test | 50 transactions / PoPE verification |
| ☐ Smart-contract audit, round 1 results | Address feedback |
| ☐ MORM Initial Airdrop whitelist criteria published | Full transparency |
| ☐ AI Moderation Agent benchmark | False-positive/negative rates |
| ☐ DEX liquidity bootstrap planning | Uniswap, Raydium candidates |

**KPI**: Validators 500, Testnet TX 100K, Discord 75K

### November 2026

| Item | Detail |
|---|---|
| ☐ MORM Cells 50%/10% cycle production-ready | Perceived latency <300ms |
| ☐ Generation ID (C2PA-compliant) prototype | Adobe CAI compatibility test |
| ☐ V-Hash + audio FP integrated | Large-scale dedup benchmark |
| ☐ Bug Bounty initial rewards | Via Smart Contract |
| ☐ Audit, round 2 results | OpenZeppelin |
| ☐ AI Agent load test | 100K concurrent |

**KPI**: Validators 1,000, Testnet videos 100K, Discord 100K

### December 2026

| Item | Detail |
|---|---|
| ☐ Audits final pass, code freeze | Zero critical issues |
| ☐ TGE prep: DEX liquidity bootstrap final plan | $5M-equivalent initial liquidity |
| ☐ MORM Initial Airdrop snapshot | TGE -30 days |
| ☐ Admin key Renounce prep (except Bridge/Multi-sig) | Final community check |
| ☐ AI Agent production candidates finalized (5 types) | DAO first-vote approval |

**KPI**: Validators 1,500, Discord 150K, Waitlist 500K

### January 2027: **TGE**

| Item | Detail |
|---|---|
| ☐ **MORM Mainnet launch** | DAG consensus production |
| ☐ **MORM Token TGE** | Liquidity pool open (DEX-centric) |
| ☐ **MORM Initial Airdrop distribution** | 500M MORM distributed |
| ☐ **PoUW rewards begin** | Reward Distributor live |
| ☐ **AI Agents go production** | 5 types fully operational |
| ☐ DEX listings (Uniswap, Raydium, etc.) | Day 0, smart-contract bootstrap |
| ☐ **All admin keys renounced** | Except Bridge/Multi-sig |
| ☐ **DAO voting Live** | First minor-parameter vote |

**KPI**: Mainnet Validators 2,000, Day-1 volume $5M, Token Holders 50K

### February 2027

| Item | Detail |
|---|---|
| ☐ **MORM Phase 1 begins** (Closed β, 10K invitees) | Initial Airdrop recipients |
| ☐ **MORM Shop commercial activation** | Limited categories / regions |
| ☐ Validator Tier system live | Creator / Publisher / Pioneer |
| ☐ AI Marketing Agent deploy | Multi-language posting begins |
| ☐ AI Translation Agent deploy | 5-language localization auto-sync |
| ☐ DAO Tier 2 voting implemented | Mid-size parameter votes begin |

**KPI**: Active users 50K, first Shop tx 100, Discord 200K

### March 2027 (Gate B end)

| Item | Detail |
|---|---|
| ☐ Closed β expansion (50K) | Asia + North America |
| ☐ MORM iOS/Android v1.0 (β) | TestFlight, Internal Testing, PWA in parallel |
| ☐ Initial 100 Verified Creators | Invite + AI Audit Coordinator |
| ☐ First viral video case | 1M+ views |
| ☐ AI Compliance Agent deploy | Large-tx KYC orchestration begins |

**KPI**: MAU 100K, Validators 5K, Shop cumulative 1K

---

## 4. MORM Phase 1 (2027/04 – 2027/12)

**Goal**: Closed β → Open β. Creator economy in full swing. AI Agents fully deployed.

### 2027 Q2 (Apr-Jun): acceleration

| Month | Milestones |
|---|---|
| Apr | iOS/Android v1.0 official, Verified Creators 500, MAU 200K |
| May | MORM Studio v1.0 (creator editor), MAU 350K |
| Jun | TGE 1st anniversary, Creators 1K, MAU 500K, Initial Airdrop retro |

**Q2-end KPI**: MAU 500K, Validators 10K, cumulative videos 1M, Shop monthly tx 10K

### 2027 Q3 (Jul-Sep): expansion

| Month | Milestones |
|---|---|
| Jul | MORM AI Lab β (generative AI service), Indonesia/Philippines launch |
| Aug | India, Vietnam added; MORM Live α (live streaming) |
| Sep | Backers cliff ends, first vesting unlock, MAU 1M |

**Q3-end KPI**: MAU 1M, Validators 25K, active nodes 50K, Shop monthly 50K

### 2027 Q4 (Oct-Dec): completion

| Month | Milestones |
|---|---|
| Oct | DAO governance production (Snapshot migration), Pioneer Tier opens |
| Nov | MORM Live v1.0, AI Bug Triage Agent live, MAU 1.5M |
| Dec | MORM Phase 1 complete, Phase 2 prep, MAU 2M, audit re-run |

**Q4-end KPI (Gate C)**: MAU 2M, Validators 50K, nodes 100K, Shop cumulative 1M

---

## 5. MORM Phase 2 (2028/01 – 2028/12)

**Goal**: Public Launch, global rollout, ecosystem expansion.

### 2028 Q1: Public Launch

| Month | Milestones |
|---|---|
| Jan | **MORM Public Launch** (invite-only lifted), Translation Agent delivers 5-language localization (EN/JA/ES/PT/ID) |
| Feb | App Store / Google Play approval (via individual contributors), PWA in parallel |
| Mar | MAU 5M, Validators 100K, peak media coverage |

**Q1-end KPI**: MAU 5M, nodes 200K, cumulative videos 100M

### 2028 Q2: Live & Hardware

| Month | Milestones |
|---|---|
| Apr | MORM Hardware (dedicated camera, node devices) partner reveals |
| May | MORM Live v2.0, full live-commerce integration |
| Jun | MAU 10M |

**Q2-end KPI**: MAU 10M, live viewing 100M hours/month

### 2028 Q3: SDK & Bridges

| Month | Milestones |
|---|---|
| Jul | **MORM SDK release** (third-party dApp dev kit) |
| Aug | wMORM bridges to Ethereum / Solana |
| Sep | 100+ third-party dApps |

**Q3-end KPI**: MAU 20M, Bridge cumulative $1B

### 2028 Q4: Global Reach

| Month | Milestones |
|---|---|
| Oct | LATAM / Africa rollout (Translation Agent adds 10 languages) |
| Nov | Education / B2B partnerships announced |
| Dec | MAU 50M, nodes 1M, TGE 2nd anniversary |

**Q4-end KPI (Gate D)**: MAU 50M, nodes 1M, Shop cumulative 10M

---

## 6. MORM Phase 3 (2029+)

**Goal**: Fully autonomous operation, new domains, founding-contributor fade-out.

### 2029

| Quarter | Milestones |
|---|---|
| Q1 | MORM Spatial (VR/AR video) α, B2B/Enterprise begins |
| Q2 | MORM IoT, Bitcoin Lightning Bridge |
| Q3 | MAU 100M, total nodes across tiers 10M |
| Q4 | Bridge cumulative $10B, Treasury Multi-sig signer rotation begins |

### 2030

| Quarter | Milestones |
|---|---|
| Q1-Q2 | DAO-led major protocol evolution, founding-contributor fade-out announcement |
| Q3-Q4 | MAU 200M, full autonomy achieved, 5-year KPIs hit |

### 2031+

- Fully autonomous DAO + AI Agent operation
- Second-generation AI Agents (community-led upgrade competition)
- Founding contributors continue as single participants

---

## 7. Cross-cutting Tracks (parallel)

### 7.1 Compliance & Regulatory Watch (AI Legal Research Agent)

| Period | Detail |
|---|---|
| 2026 Q2 | Regulatory baseline (JP/US/EU/SG) |
| 2026 Q3-Q4 | TGE securities-classification self-check (Howey test, etc.) |
| 2027 full | Phased KYC (by tx size, via Compliance Agent) |
| 2027 Q4 | EU MiCA monitoring (impact assessment) |
| 2028 full | Per-jurisdiction opt-out refinement |
| 2029+ | DAO legal wrapper (DAO LLC etc.) — DAO vote |

### 7.2 Smart Contract Audits

| Timing | Detail |
|---|---|
| 2026 Q3 | Internal review, static analysis (auto-bot) |
| 2026 Q4 | External audit #1 (OpenZeppelin etc., via Audit Coordinator Agent) |
| 2026 Q4 | External audit #2 (Trail of Bits etc.) |
| Pre-TGE | Bug Bounty 30-day lockdown |
| Every 6mo post-TGE | Continuous audits (DAO budget) |
| Each major upgrade | Audit per upgrade |

### 7.3 Community Growth

| Month | Discord | X | Waitlist/MAU |
|---|---|---|---|
| 2026/04 | 500 | 1K | 0 |
| 2026/06 | 5K | 10K | 30K |
| 2026/09 | 50K | 100K | 200K |
| 2026/12 | 150K | 300K | 500K |
| 2027/03 (TGE+) | 200K | 500K | 100K MAU |
| 2027/06 | 300K | 1M | 500K MAU |
| 2027/12 | 500K | 2M | 2M MAU |
| 2028/06 | 1M | 5M | 10M MAU |
| 2028/12 | 2M | 10M | 50M MAU |
| 2029/12 | 5M | 25M | 100M MAU |

### 7.4 Marketing & PR (AI Marketing Agent)

| Phase | Strategy |
|---|---|
| Pre-Launch | Community seeding, tech press |
| Phase 0 | Crypto-native press (CoinDesk, The Block), Twitter influencers |
| Phase 1 | Mainstream tech press (TechCrunch, The Verge), AMA series |
| Phase 2 | Mainstream press, TV, regional press in emerging markets |
| Phase 3 | Global cultural moments |

All routine posts auto-generated by AI Marketing Agent. Major announcements DAO-approved.

### 7.5 Hardware Track

| When | Milestone |
|---|---|
| 2026 Q4 | Hardware Working Group launch (community DAO subcommittee) |
| 2027 Q3 | Dedicated node-device prototype |
| 2028 Q1 | Dedicated camera spec finalized (PoPE-optimized) |
| 2028 Q3 | Hardware partners begin volume production |
| 2029 Q1 | MORM Hardware store launch |

### 7.6 AI Agent Evolution

| When | Milestone |
|---|---|
| 2026 Q3 | AI Agents core 5 types deploy (Testnet) |
| 2026 Q4 | AI Agent production candidates finalized |
| 2027 Q1 | TGE: 5 types in production |
| 2027 Q2 | Marketing/Translation/Compliance Agents added |
| 2027 Q4 | Bug Triage / Legal Research / Education Agents added |
| 2028 Q1 | Audit Coordinator Agent added (10 types fully operational) |
| 2028 Q3+ | DAO-led Agent competitive proposal system begins |
| 2029+ | Second-generation AI Agents |

---

## 8. Economic Milestones

### 8.1 Token Holders

| When | Target |
|---|---|
| TGE Day 0 (2027/01) | 50K |
| TGE +6mo | 200K |
| TGE +12mo | 500K |
| TGE +24mo | 5M |
| TGE +36mo | 20M |

### 8.2 Staking Ratio

| When | Target | Estimated APY |
|---|---|---|
| MORM Phase 0 | 30% | 18-25% |
| MORM Phase 1 | 40% | 12-18% |
| MORM Phase 2 | 50% | 8-12% |
| MORM Phase 3 | 55% | 5-8% |

### 8.3 Shop GMV

| When | Monthly GMV target |
|---|---|
| 2027 Q1 | $100K |
| 2027 Q4 | $5M |
| 2028 Q4 | $50M |
| 2029 Q4 | $500M |
| 2030 Q4 | $5B |

### 8.4 Treasury Balance (DAO Multi-sig)

| When | Estimated operating Treasury |
|---|---|
| TGE | $10M (incl. liquidity) |
| TGE +12mo | $50M |
| TGE +24mo | $200M |
| TGE +36mo | $500M |

---

## 9. Risk Triggers & Contingency

If any trigger fires during a milestone, execute the response plan.
**Without a legal entity, response runs purely through Smart Contract + AI Agent + DAO vote.**

### 9.1 Regulatory Shock

**Trigger**: Major jurisdiction bans similar protocols, or $MORM is classified as a security.
**Action**:
- AI Compliance Agent immediately blocks regional access
- DAO vote for Treasury reallocation (48h Tier 3)
- Continue ops in remaining jurisdictions
- AI Legal Research Agent analyzes alternative jurisdictions

### 9.2 Technical Failure

**Trigger**: Major hack, consensus failure, PoPE bypass.
**Action**:
- **Emergency Multi-sig 5/7 sigs Pause**
- Impact assessment + remediation plan within 48h
- Compensation scheme via Treasury (DAO Tier 3 vote)
- Re-audit before reopening (via Audit Coordinator Agent)

### 9.3 User Acquisition Shortfall

**Trigger**: Phase KPI (MAU) below 50% of target for 60+ days.
**Action**:
- AI Marketing Agent additional budget (DAO vote)
- Product pivot consideration (DAO Tier 3)
- Strengthen partnerships (recruit via Bounty Contract)
- Public delay announcement

### 9.4 Token Price Volatility

**Trigger**: $MORM price drops 50%+ from 30-day average, or irrational spike.
**Action**:
- AI Treasury Agent proposes liquidity injection
- Temporary node-reward coefficient adjustment (DAO Tier 1, 48h)
- Expand stablecoin payment options

### 9.5 Competitive Pressure

**Trigger**: Existing platforms copy MORM core features.
**Action**:
- Defensive PoPE patent consideration (DAO Tier 3)
- Accelerate differentiator releases (additional bounties)
- Strengthen unique-brand campaigns (Marketing Agent budget up)

### 9.6 AI Agent Runaway

**Trigger**: AI Agent makes unexpected judgements (mass mis-moderation, false slashing).
**Action**:
- Emergency Multi-sig immediately halts the affected Agent
- Auto-failover to backup Agent
- DAO Tier 3 vote to repair / replace

### 9.7 Treasury Multi-sig Signer Compromise

**Trigger**: Signer trust issue, or 3+ of 7 simultaneous departures.
**Action**:
- DAO Tier 3 emergency vote selects replacement signers
- Migrate existing Multi-sig to new addresses
- Remaining signers manage transition

---

## 10. KPI Dashboard (AI Analytics Agent)

### 10.1 Real-time monitoring (public)

`https://transparency.morm.network` (planned), 24/7:

- Active nodes (per Tier)
- Active Viewers / Creators / Publishers / Pioneers
- Video uploads (24h / 7d / 30d)
- MORM Token price and liquidity
- Shop tx count and GMV
- Fraud-detection rate, Slash count
- Avg. playback start time
- Total network tx throughput
- AI Agent decision logs
- Treasury fund movements

### 10.2 Weekly review (public to DAO)

- Discord / X growth
- New user registrations
- Video completion rate
- Cross-tier transitions
- Bug reports and SLA
- AI Agent response latency / error rate

### 10.3 Monthly strategy (DAO vote inputs)

- Phase Gate progress
- Treasury balance and spend
- Legal / regulatory developments (via Legal Research Agent)
- Competitive landscape
- Partnership progress
- AI Agent performance review

### 10.4 Quarterly strategy

- KPI dashboard full review
- Roadmap revision (DAO Tier 3 vote)
- Major decisions (DAO votes)
- Treasury reallocation

---

## 11. Progress Reporting Format

### 11.1 Public roadmap update (monthly, AI Marketing Agent posts)

Published end-of-month on official site and X / Discord:

- Completed milestones (checklist)
- In-progress items (% complete)
- Delayed items (reason + plan)
- Next month's priorities
- KPI actuals vs targets

### 11.2 Quarterly report (auto-posted to DAO forum)

- Phase status
- Financial position (incl. Treasury)
- DAO major resolutions
- Next quarter's focus

### 11.3 Annual report (community-approved)

- Full Phase review
- DAO vote record
- Partnership / integration record
- Next year's strategy

---

## 12. Upside Scenarios (pull-forward triggers, DAO Tier 3 vote)

If the following occur, consider pulling milestones forward:

- **Crypto bull market** → TGE pull-forward, marketing budget increase
- **Major-platform misstep** → user influx opportunity, expand AI Support Agent
- **Media virality** → scale ahead of plan, strengthen AI Compliance Agent
- **Major partnership** → hardware OEM, accelerate global rollout
- **Regulatory tailwind (EU AI Act, etc.)** → leverage Generation ID advantage

---

## 13. Critical Premise: "No Legal Entity" Design

This milestone document presumes "no legal entity." Operationally:

| Traditional PM work | MORM equivalent |
|---|---|
| Employment contracts / payroll | ❌ Not needed (Bounty Contract) |
| Corporate tax filing | ❌ Not needed (no protocol-level tax obligation) |
| Bank account management | ❌ Not needed (crypto-native) |
| Office leases | ❌ Not needed (remote) |
| Investor Relations | ⚠️ Limited (AMA + transparency dashboard) |
| Executive meetings | ❌ Replaced by DAO votes |
| Trademark filings | ⚠️ DAO files (where DAO LLC permitted, e.g., Wyoming) |
| App Store registration | ⚠️ Individual contributors as personal developers |

See [AGENTS.md](AGENTS.md) §6 for details.

---

## Revision History

- **2026-04-26 v0.4** — Reflected PoC Phase 1-27f completion (46 items, DAG/QUIC/BFT/Multi-sig/Web hardening/Tx confirm dialog all done, SECURITY §5 must-have OK = mainnet candidate minimum requirements met)
- **2026-04-25 v0.3** — Reflected PoC Phase 1-23a completion, added Implementation Status section at top
- **2026-04-25 v0.2** — No-entity design, AI Agent-centric, Phase rename (Genesis→Phase 0, etc.)
- **2026-04-25 v0.1** — Initial draft

---

*This is an internal planning document. When publishing externally, edit and extract appropriately. Milestones revised flexibly. Delays/changes will be transparently disclosed.*

# MORM AI Agent Architecture

**Version**: 0.1 (Draft)
**Date**: 2026-04-25
**Status**: Design draft

---

## 0. Design Principle

MORM **has no legal entity** (no Corporation / Foundation / DAO LLC).
There is no central operating team. No CEO. No headquarters.

Operations run on three layers:

```
┌─────────────────────────────────────────┐
│    Layer 3: DAO (token holders)         │  ← parameter setting
├─────────────────────────────────────────┤
│    Layer 2: AI Agents                   │  ← autonomous daily ops
├─────────────────────────────────────────┤
│    Layer 1: Smart Contracts             │  ← immutable money flow
└─────────────────────────────────────────┘
```

The DAO sets parameters. AI Agents execute daily operations within those parameters. Smart Contracts enforce immutable fund movement and sanctions. **There is no room for centralized human authority.**

---

## 1. Why No Legal Entity

### 1.1 Philosophical reason

The MORM Manifesto declares "a swarm with no center." Holding a legal entity creates that center physically.

### 1.2 Practical reasons

| Risk of having a legal entity | MORM's response |
|---|---|
| Subordinate to one jurisdiction's regulation | Neutral across all jurisdictions |
| Can be ordered to halt by a specific government | Cannot be halted |
| Direction shifts via management decision | Only DAO can change |
| Collapses on founder/exec scandal | Resilient via absence of individuals |
| Pressure to raise fees (shareholder demand) | 1% is permanently immutable |

### 1.3 Reference Models

- **Bitcoin**: no entity, Satoshi anonymous, protocol autonomous
- **Ethereum L1 core**: Ethereum Foundation exists but the protocol cannot be stopped
- **Uniswap Protocol**: Uniswap Labs exists but the Protocol is headless by design
- **Tornado Cash**: no entity — but US Treasury sanctioned it (a real-world risk example)

MORM treats Bitcoin / Uniswap Protocol / various DAOs as reference models.

---

## 2. Smart Contract Layer (Layer 1)

All fund flows are executed by smart contracts. No admin keys. No pause keys.

### 2.1 Major Contracts

| Contract | Role | Immutability |
|---|---|---|
| **MORM Token** | 10B fixed supply, issuance/distribution logic | Fully immutable |
| **Reward Distributor** | Node rewards via PoUW | Parameters DAO-tunable |
| **Escrow Contract** | 99% lock & release for Shop transactions | Logic immutable; disputes via DAO |
| **Slash Engine** | Auto-confiscation on detected fraud | Detection via AI Agent |
| **Burn Contract** | Burn mechanism | Rates DAO-tunable |
| **Bounty Contract** | Pays core contributors | DAO-budgeted |
| **DAO Voting** | Governance votes | Immutable |
| **Bridge Contract** | wMORM mint/burn | Multi-sig + DAO oversight |

### 2.2 No Admin Keys

After deployment, all contracts have their admin keys burned (Renounce Ownership). Exceptions:

- Bridge Contract (multi-sig + DAO oversight)
- Treasury Multi-sig (DAO-vote activated)

Otherwise, no human can manually intervene.

---

## 3. AI Agent Layer (Layer 2)

Daily operations are executed by AI Agents. Each Agent:

- Operates only within parameters **approved by DAO vote**
- Records all actions **on-chain** (transparency)
- Can be **swapped/upgraded by DAO** at any time (open source)

### 3.1 Agent Catalog

#### 🛡️ Moderation Agent

**Role**:
- V-Hash duplicate check on uploads
- Generation ID verification (C2PA compliant)
- AI pre-screening for inappropriate content (CSAM, etc.)
- Tampered video detection (PoPE violations)

**Implementation**: Dedicated GPU cluster (running on NodePower) + open-source AI models
**DAO control**: Moderation thresholds, model selection

#### 💰 Treasury Agent

**Role**:
- Auto-execution of DAO-approved budgets
- Liquidity pool optimization (auto market-making)
- Bug Bounty payment automation
- Emergency multi-sig activation proposals

**Implementation**: Multi-sig + AI signing proposals
**DAO control**: Monthly budget caps, emergency thresholds

#### 🎫 Support Agent

**Role**:
- 24/7 multi-language user support
- Bug-report triage and escalation to Bug Bounty Contract
- Auto-update FAQ
- Initial dispute handling

**Implementation**: Claude / GPT-4o / Gemini-class models + RAG over docs
**DAO control**: Response tone, escalation criteria

#### 📢 Marketing Agent

**Role**:
- Official posting on X / Discord / Telegram
- Multi-language translation and rollout
- Community event announcements
- AMA logistics support

**Implementation**: Multi-language LLM + social scheduler
**DAO control**: Tone/message policy, banned-phrases list
**Note**: Routine posts auto-generated; major announcements DAO-approved

#### ⚖️ Legal Research Agent

**Role**:
- Monitor crypto regulation across jurisdictions
- Early-warning on material regulatory changes
- Propose Terms updates (to DAO)
- Assist regional opt-out judgments

**Implementation**: Regulatory DBs (e.g., Bloomberg Law) + LLM analysis
**DAO control**: Watch-list jurisdictions, alert thresholds

#### 🔍 Compliance Agent

**Role**:
- Orchestrate KYC for large transactions
- Integrate with third-party KYC providers (Sumsub, etc.)
- Sanctions-address watch (Chainalysis, etc.)
- Suspicious-pattern detection

**Implementation**: API integrations (Sumsub, Chainalysis, TRM Labs)
**DAO control**: KYC thresholds, target jurisdictions

#### 🐛 Bug Triage Agent

**Role**:
- Security-impact judgement on bug reports
- Bounty amount proposal (Critical/High/Medium/Low)
- Duplicate-report consolidation
- Patch-proposer incentive calc

**Implementation**: Bug-bounty platform integration (Immunefi) + custom classifier
**DAO control**: Reward table, judgement criteria

#### 🌐 Translation Agent

**Role**:
- Auto-sync docs/UI across languages
- Initial draft for newly added languages
- Hand off to native reviewers (community bounties)

**Implementation**: GPT-4o / Claude + translation memory + community bounty bridge
**DAO control**: Supported languages, quality bar

#### 📊 Analytics Agent

**Role**:
- Network-wide KPI dashboard
- Anomaly detection (sudden user drop, token-price moves, etc.)
- Auto-generated DAO reports
- Public transparency dashboard

**Implementation**: On-chain data + Web2 API integration
**DAO control**: Monitored metrics, alert thresholds

#### 🎓 Education Agent

**Role**:
- Interactive guide for new users
- Node setup support
- First-time Walletless ID setup help
- Multi-language Q&A

**Implementation**: LLM + RAG + voice support
**DAO control**: Content updates, scenario coverage

#### 🤖 Audit Coordinator Agent

**Role**:
- Coordinate with third-party audit firms via Smart Contracts
- Propose audit scope
- Report findings to DAO
- Issue bounties for fixes

**Implementation**: Audit-firm APIs + contract templates
**DAO control**: Firm selection, budget

### 3.2 Agent-to-Agent Coordination

Each Agent operates independently but coordinates on events:

```
[Moderation Agent] detects violation
   ↓ on-chain report
[Slash Engine Smart Contract] auto-slashes
   ↓
[Treasury Agent] proposes victim restitution
   ↓ DAO vote (24h)
[Bounty Contract] disburses restitution
   ↓
[Support Agent] notifies parties
   ↓
[Analytics Agent] records the incident
```

### 3.3 Agent Replaceability

DAO can vote to swap Agents. This enables:
- Keeping pace with AI advancement
- Avoiding lock-in to a specific model
- Open competition among proposed Agents

```
DAO vote → "Swap Moderation Agent from Claude 5 to Llama 6"
   ↓
2-week migration window
   ↓
New Agent obtains on-chain attestation
   ↓
Old Agent halts; new Agent runs production
```

---

## 4. DAO Layer (Layer 3)

### 4.1 Voting Power

| Unit | Power |
|---|---|
| **1 MORM = 1 vote** | Base rule |
| **Holding-period bonus** | × 1.2 after 6mo, × 1.5 after 12mo |
| **Pioneer Tier bonus** | × 1.3 for long-term contributors |
| **Per-address cap** | 1% of total voting power |

### 4.2 Vote Scope

#### Tier 1: Minor parameters (48h vote, 3% quorum)

- Node-reward weighting coefficients
- Spam-threshold fine-tuning
- AI Agent response-template updates

#### Tier 2: Mid-size parameters (7-day vote, 10% quorum)

- Burn-rate adjustments
- AI Agent body swaps
- New language support
- Ecosystem Fund allocation

#### Tier 3: Major decisions (14-day vote, 20% quorum)

- Add/remove AI Agents
- Deploy new Smart Contracts
- Add bridges
- Large Treasury spends (>$1M-equivalent)

#### Tier 4: Immutable (no vote)

- 10B total supply
- 1% fee
- User-owned data principle
- Walletless ID principle
- PoPE mandatory principle

### 4.3 Voting Process

```
[Anyone can propose]
   ↓ 1,000 MORM stake (proposal deposit)
[7-day discussion]
   ↓ Discord / forum
[Voting period (per Tier)]
   ↓ Snapshot or on-chain vote
[Pass]
   ↓ 24-72h Timelock
[Smart Contract executes / Agent updates]
   ↓
[Result recorded]
```

### 4.4 Emergency Response

For situations too urgent for DAO process (major hacks, etc.):

- **Emergency Multi-sig** (5/7 sigs) can pause
- Signers: geographically distributed across continents
- Within 72h, DAO formally ratifies/cancels
- Signers chosen from trusted community members

---

## 5. Core Contributors

### 5.1 "Contributors," not "Employees"

- No employment contracts
- No salaries
- All compensation via **Smart Contract Bounty**
- Participate as individuals or independent contractors
- Tax compliance is each person's own responsibility

### 5.2 Contribution Categories

| Category | Reward Source |
|---|---|
| Protocol development | Bounty Contract (DAO budget) |
| AI Agent development | Bounty Contract |
| Documentation | Bounty Contract + translation bounty |
| Legal research | Bounty Contract |
| Bug fixes | Bug Bounty Contract |
| Validator operations | PoUW reward |
| Community ops | Quest System reward |

### 5.3 Anonymous / Pseudonymous OK

All contributors may participate anonymously or pseudonymously. Given Tornado Cash precedent, anonymity is recommended especially for those touching critical parameters.

### 5.4 Founding Contributor

The bootstrapping role is publicly attributed to **YACHIDA** as *Founding Contributor*.

Responsibilities:
- Deploy initial Smart Contracts
- Publish initial AI Agents (open source)
- Set initial DAO parameters
- Execute TGE

After TGE, the Founding Contributor transitions to **equal standing** with other core contributors, holding no operational authority, no special voting weight, and no additional token allocation. "Founding Contributor" records the historical fact of igniting the network — it is not a CEO/Founder operational role (cf. Bitcoin / Satoshi Nakamoto model).

---

## 6. What Cannot Be Done Without an Entity (constraints)

Honest list:

### 6.1 Constraints

| Function | Reason | MORM response |
|---|---|---|
| Open a bank account | No entity | Not needed (crypto-native) |
| Sign with traditional audit firms | No legal counterparty | Use crypto-native firms (OpenZeppelin, Code4rena, etc.) |
| Register as App Store developer | Need individual or entity | Individual contributors register; PWA primary |
| Retain traditional law firms | No counterparty | Per-case bounty engagements |
| Apply to centralized exchanges | Required legal counterparty | DEX-only at start; CEX listings at exchange discretion |
| Trademark filings | No applicant | DAO files (where DAO LLC is permitted) |

### 6.2 Gray Areas

- **VASP registration**: required in some jurisdictions, but headless protocol may be out of scope
- **Tax**: each individual user's responsibility; no protocol-level tax
- **GDPR compliance**: handled via AI Agent automated processing with explicit consent

### 6.3 Opt-out

If a jurisdiction declares the protocol illegal:
- AI Agent technically blocks regional access
- DAO votes regional policy
- Users self-responsibly use VPNs (not recommended)

---

## 7. Roadmap: Agent Deployment

### MORM Phase 0 (until TGE)

**Pre-TGE**:
- Deploy 5 core AI Agents (Moderation / Treasury / Support / Analytics / Education)
- Initial Smart Contract set (Token / Distributor / Bounty / DAO Voting)
- Audit Coordinator Agent commissions third-party audits

**At TGE**:
- All admin keys renounced (except Bridge / Multi-sig)
- Authority migrated to DAO
- AI Agents go live in production

### MORM Phase 1

- Add Marketing / Translation Agents
- Integrate Compliance Agent
- Legal Research Agent goes full operation

### MORM Phase 2

- Bug Triage Agent enhanced
- Each Agent's performance reviewed and DAO-led upgrades
- Open competitive proposal system for Agents

### MORM Phase 3

- Fully autonomous operation
- Original contributors are mere participants
- Evolution to second-generation AI Agents

---

## 8. Transparency & Accountability

### 8.1 All Open Source

- AI Agent code (GitHub, AGPL-3.0)
- Smart Contract code (GitHub, MIT)
- Documentation (GitHub, CC-BY-4.0)
- Agent decision logs (on-chain or IPFS)

### 8.2 Where Responsibility Lies

Traditional "management responsibility" does not exist. Instead:

| Responsibility | Bearer |
|---|---|
| Smart Contract code bugs | Code contributors + Bug Bounty rewards |
| AI Agent judgement errors | DAO-led Agent rework |
| Illicit-content circulation | Moderation Agent + Slash Engine |
| User-vs-user disputes | DAO arbitration |
| Regulatory violation | User self-responsibility + Compliance Agent |

### 8.3 Audit Dashboard

Real-time public:
- All Agent decision logs
- All Treasury fund movements
- All Slash executions
- All DAO votes
- All Bug Bounty payouts

URL: `https://transparency.morm.network` (planned)

---

## 9. Risks & Mitigations

### 9.1 AI Agent runaway

**Mitigation**:
- Strict parameter bounds (DAO-set)
- Multi-Agent redundancy (critical decisions require multi-Agent consensus)
- Pause via Emergency Multi-sig

### 9.2 DAO governance attack

**Mitigation**:
- Anti-whale (1% cap)
- Holding-period bonus (suppresses short-term speculators)
- Tiered quorum (more critical = higher quorum)
- 24-72h timelock

### 9.3 Regulatory risk

**Mitigation**:
- Per-jurisdiction opt-out
- Anonymous/pseudonymous contributor protection (Tornado Cash lesson)
- Voluntary KYC via Compliance Agent (large tx only)

### 9.4 AI model lock-in

**Mitigation**:
- All Agents replaceable
- Phased migration to open-source models
- DAO-vote model selection

---

## 10. Pragmatic Compromises

"Fully entity-less" is the ideal. Pragmatic compromises:

### 10.1 Treasury Multi-sig signers

Fully headless makes emergency response hard. Maintain a minimal human signer set:
- 5/7 multi-sig
- Geographic distribution
- DAO-elected and DAO-removable

### 10.2 Domain management

`morm.network` etc. live under centralized ICANN. Response:
- Use ENS / Unstoppable Domains in parallel
- Major domains under multi-sig

### 10.3 App store distribution

Apple / Google reviews require a legal responsible party. Response:
- Individual contributors register as personal developers
- PWA-first (Progressive Web App)
- F-Droid / direct APK distribution in parallel

These exceptions to the "no entity" principle are documented in TERMS.md and governance docs.

---

## 11. Glossary

- **Layer 1 (Smart Contract)**: fund-flow execution
- **Layer 2 (AI Agent)**: autonomous daily ops
- **Layer 3 (DAO)**: parameter setting
- **Admin key**: central operator's intervention right (burned in MORM)
- **Renounce Ownership**: permanently burn admin key
- **Bounty Contract**: pays contributors
- **Emergency Multi-sig**: emergency-pause authority (5/7, geo-distributed)

---

*This is a design draft. At implementation, individual Agent specs will be split into separate documents.*

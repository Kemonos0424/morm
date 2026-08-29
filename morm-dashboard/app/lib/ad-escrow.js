import { dbExec, dbRun, dbGet, dbAll } from '@/app/lib/db';
import { unitsToMorm } from '@/app/lib/morm-units';
import { transferMorm, mormL1Enabled } from '@/app/lib/morm-l1';
import { ensureWalletSchema, recordTx } from '@/app/lib/wallet-schema';

// Phase 2-⑥ — AD escrow triangle. Advertiser deposit → escrow → serving nodes /
// creators. This is REDISTRIBUTION of the advertiser's funded budget, NOT
// treasury emission, so it never inflates supply: total campaign payouts are
// capped by campaign.funded_units. (The B_day emission budget is untouched.)
//
// Flow:
//   1. advertiser deposits MORM to the treasury (kind:6) → fundCampaign records
//      the campaign budget (admin-recorded against the on-chain deposit tx).
//   2. serving nodes / creators accrue verified ad events (impression / click),
//      each a SIGNED claim (earner proves it served), deduped.
//   3. settleCampaign pays earners ∝ weighted events at a CPM rate, from the
//      campaign budget, capped by remaining; treasury (holding the deposit)
//      sends the MORM. Idempotent per (campaign, epoch, earner).
//
// Envs: AD_UNIT_PER_WEIGHT (base units paid per impression-weight),
//       AD_CLICK_WEIGHT (a click counts as this many impression-weights).
const unitPerWeight = () => Number(process.env.AD_UNIT_PER_WEIGHT || 1000);
export const AD_CLICK_WEIGHT = () => Number(process.env.AD_CLICK_WEIGHT || 20);

let ensured = false;
export async function ensureAdSchema() {
  if (ensured) return;
  await dbExec(`
    CREATE TABLE IF NOT EXISTS ad_campaigns (
      id           TEXT PRIMARY KEY,
      advertiser   TEXT,
      funded_units INTEGER NOT NULL DEFAULT 0,
      spent_units  INTEGER NOT NULL DEFAULT 0,
      deposit_tx   TEXT,
      status       TEXT DEFAULT 'active',
      created_at   INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ad_events (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id TEXT NOT NULL,
      earner_addr TEXT NOT NULL,
      kind        TEXT NOT NULL,
      ref         TEXT NOT NULL,
      weight      INTEGER NOT NULL DEFAULT 1,
      settled     INTEGER NOT NULL DEFAULT 0,
      created_at  INTEGER NOT NULL,
      UNIQUE(campaign_id, kind, ref, earner_addr)
    );
    CREATE INDEX IF NOT EXISTS idx_ad_events_campaign ON ad_events(campaign_id, settled);
    CREATE TABLE IF NOT EXISTS ad_payouts (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id TEXT NOT NULL,
      epoch_label TEXT NOT NULL,
      earner_addr TEXT NOT NULL,
      units       INTEGER,
      tx_hash     TEXT,
      status      TEXT DEFAULT 'pending',
      created_at  INTEGER NOT NULL,
      UNIQUE(campaign_id, epoch_label, earner_addr)
    );
  `);
  ensured = true;
}

// 1) record an advertiser deposit as campaign budget (admin-gated upstream).
export async function fundCampaign({ campaignId, advertiser, units, depositTx }) {
  await ensureAdSchema();
  const now = Math.floor(Date.now() / 1000);
  const add = Math.max(0, Math.floor(Number(units) || 0));
  await dbRun(
    `INSERT INTO ad_campaigns (id, advertiser, funded_units, spent_units, deposit_tx, status, created_at)
       VALUES (?, ?, ?, 0, ?, 'active', ?)
     ON CONFLICT(id) DO UPDATE SET funded_units = funded_units + ?, deposit_tx = ?`,
    [campaignId, advertiser || null, add, depositTx || null, now, add, depositTx || null]
  );
  return getCampaign(campaignId);
}

export async function getCampaign(campaignId) {
  await ensureAdSchema();
  const c = await dbGet(`SELECT * FROM ad_campaigns WHERE id = ?`, [campaignId]);
  if (!c) return null;
  return { ...c, remaining_units: Number(c.funded_units) - Number(c.spent_units) };
}

// 2) accrue a verified ad event. Dedup by (campaign, kind, ref, earner).
// Returns { ok:true, weight } or { ok:false, duplicate:true }.
export async function recordAdEvent({ campaignId, earner, kind, ref }) {
  await ensureAdSchema();
  const weight = kind === 'click' ? AD_CLICK_WEIGHT() : 1;
  const now = Math.floor(Date.now() / 1000);
  const r = await dbRun(
    `INSERT OR IGNORE INTO ad_events (campaign_id, earner_addr, kind, ref, weight, settled, created_at)
       VALUES (?, ?, ?, ?, ?, 0, ?)`,
    [campaignId, earner, kind, ref, weight, now]
  );
  const won = Number(r?.rowsAffected ?? r?.changes ?? 0) > 0;
  return won ? { ok: true, weight } : { ok: false, duplicate: true };
}

// 3) settle a campaign epoch: pay earners ∝ unsettled weight at the CPM rate,
// capped by remaining budget (scaled down if the round would overspend).
export async function settleCampaign({ campaignId, epochLabel, dryRun = false }) {
  if (!campaignId || !epochLabel) throw new Error('campaignId and epochLabel required');
  await ensureAdSchema();
  const camp = await getCampaign(campaignId);
  if (!camp) return { error: 'campaign not found' };
  const remaining = Number(camp.funded_units) - Number(camp.spent_units);
  if (remaining <= 0) return { ok: true, campaignId, epochLabel, earners: 0, units: 0, remaining: 0, note: 'budget exhausted' };

  const rows = await dbAll(
    `SELECT id, earner_addr, weight FROM ad_events WHERE campaign_id = ? AND settled = 0`, [campaignId]);
  if (!rows.length) return { ok: true, campaignId, epochLabel, earners: 0, units: 0, remaining };

  const per = {};
  for (const r of rows) {
    const d = per[r.earner_addr] || (per[r.earner_addr] = { weight: 0, ids: [] });
    d.weight += Number(r.weight); d.ids.push(r.id);
  }
  const totalWeight = Object.values(per).reduce((s, d) => s + d.weight, 0);
  const rate = unitPerWeight();
  let totalDue = totalWeight * rate;
  // scale down to fit remaining budget if the round would overspend
  const scale = totalDue > remaining ? remaining / totalDue : 1;

  const plan = Object.entries(per).map(([earner, d]) => ({
    earner, weight: d.weight, ids: d.ids, units: Math.floor(d.weight * rate * scale),
  })).filter((p) => p.units >= 1);

  if (dryRun) return { ok: true, dryRun: true, campaignId, epochLabel, remaining, rate, totalWeight, scale, plan };
  if (!mormL1Enabled()) return { error: 'L1 payout not available' };
  await ensureWalletSchema();

  const now = Math.floor(Date.now() / 1000);
  let paidEarners = 0, unitsTotal = 0;
  for (const p of plan) {
    const done = await dbGet(`SELECT status FROM ad_payouts WHERE campaign_id=? AND epoch_label=? AND earner_addr=?`,
      [campaignId, epochLabel, p.earner]);
    if (done && done.status === 'sent') continue;
    if (!done) {
      await dbRun(`INSERT OR IGNORE INTO ad_payouts (campaign_id,epoch_label,earner_addr,units,status,created_at)
                   VALUES (?,?,?,?, 'pending', ?)`, [campaignId, epochLabel, p.earner, p.units, now]);
    }
    try {
      const mormAmount = unitsToMorm(p.units);
      const r = await transferMorm({ to: p.earner, mormAmount });
      await dbRun(`UPDATE ad_payouts SET tx_hash=?, status='sent' WHERE campaign_id=? AND epoch_label=? AND earner_addr=?`,
        [r.txHash, campaignId, epochLabel, p.earner]);
      await dbRun(`UPDATE ad_events SET settled=1 WHERE id IN (${p.ids.map(() => '?').join(',')})`, p.ids);
      await dbRun(`UPDATE ad_campaigns SET spent_units = spent_units + ? WHERE id = ?`, [p.units, campaignId]);
      await recordTx({ txHash: r.txHash, from: process.env.MORM_TREASURY_ADDRESS, to: p.earner, amount: mormAmount, kind: `ad:${campaignId}` });
      paidEarners++; unitsTotal += p.units;
    } catch (e) {
      await dbRun(`UPDATE ad_payouts SET status='failed' WHERE campaign_id=? AND epoch_label=? AND earner_addr=?`,
        [campaignId, epochLabel, p.earner]);
    }
  }
  const after = await getCampaign(campaignId);
  return { ok: true, campaignId, epochLabel, earners: paidEarners, units: unitsTotal,
           funded: Number(after.funded_units), spent: Number(after.spent_units), remaining: after.remaining_units };
}

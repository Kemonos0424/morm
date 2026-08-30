// Server-side price + pool-reserve reader for the cash-out valve. Mirrors the
// math in app/api/price/route.js (Uniswap v3 slot0 + pool token balances on
// Base mainnet) but returns the USDC reserve too, and supports env overrides
// for tests / emergencies. The public /api/price route is intentionally left
// untouched — this is a separate, valve-facing reader.
//
//   env MORM_PRICE_OVERRIDE_USD    : force usdPerMorm (test/emergency)
//   env MORM_RESERVE_USDC_OVERRIDE : force the USDC reserve (test/emergency)

const RPC   = process.env.MORM_RPC || 'https://mainnet.base.org';
const POOL  = process.env.MORM_POOL_ADDR   || '0x6615fC0239eDDb27A8fF2D774C438e68C4599A55';
const WMORM = process.env.MORM_WMORM_ADDR  || '0x7fEf327a811e73F06cccF0De9db022e739d5076d';
const USDC  = process.env.MORM_USDC_ADDR   || '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const INITIAL_RATE = 0.01;

let _id = 1;
async function rpc(method, params) {
  const r = await fetch(RPC, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0', 'Accept': '*/*' },
    body: JSON.stringify({ jsonrpc: '2.0', id: _id++, method, params }),
    cache: 'no-store',
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || 'rpc error');
  return j.result;
}

function priceFromSqrt(sqrtHex) {
  const sqrt = BigInt(sqrtHex);
  const r = Number(sqrt) / 2 ** 96;
  return (r * r) * 1e12;  // mainnet: wMORM=token0 → USDC per wMORM
}

// Returns { usdPerMorm, usdcReserve (or null if unknown), source }.
export async function getPriceReserve() {
  const ovUsd = process.env.MORM_PRICE_OVERRIDE_USD;
  const ovRes = process.env.MORM_RESERVE_USDC_OVERRIDE;
  if (ovUsd != null || ovRes != null) {
    return {
      usdPerMorm: ovUsd != null ? Number(ovUsd) : INITIAL_RATE,
      usdcReserve: ovRes != null ? Number(ovRes) : null,
      source: 'override',
    };
  }
  try {
    const balOf = (t) => rpc('eth_call', [{ to: t, data: '0x70a08231000000000000000000000000' + POOL.slice(2) }, 'latest']);
    const [s0, ru] = await Promise.all([
      rpc('eth_call', [{ to: POOL, data: '0x3850c7bd' }, 'latest']),
      balOf(USDC),
    ]);
    const usdPerMorm = priceFromSqrt('0x' + s0.slice(2, 66));
    const usdcReserve = Number(BigInt(ru)) / 1e6;
    return { usdPerMorm, usdcReserve, source: 'uniswap-v3-slot0' };
  } catch (err) {
    // Fail-safe: unknown reserve (caller uses a conservative fallback cap).
    return { usdPerMorm: INITIAL_RATE, usdcReserve: null, source: 'fallback', error: err.message };
  }
}

// Server-side price + pool-reserve reader for the cash-out valve. Mirrors the
// math in app/api/price/route.js (Uniswap v3 slot0 + pool token balances on
// Base Sepolia) but returns the USDC reserve too, and supports env overrides
// for tests / emergencies. The public /api/price route is intentionally left
// untouched — this is a separate, valve-facing reader.
//
//   env MORM_PRICE_OVERRIDE_USD    : force usdPerMorm (test/emergency)
//   env MORM_RESERVE_USDC_OVERRIDE : force the USDC reserve (test/emergency)

const RPC   = process.env.BASE_SEPOLIA_RPC || 'https://sepolia.base.org';
const POOL  = process.env.MORM_POOL_ADDR   || '0x9E62498516742EC84F3BC71cDB7b2a172dfA5789';
const WMORM = process.env.MORM_WMORM_ADDR  || '0x5cd8053c2fb44a3107109A22dD8529F67751c74C';
const USDC  = process.env.MORM_USDC_ADDR   || '0x2B6648CD0c0bd8e1e50AdCB0F154692a0F90f453';
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
  return (1e18 / (r * r)) / 1e6;
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

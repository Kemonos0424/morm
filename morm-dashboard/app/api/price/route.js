import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Public price oracle: reads the live wMORM/USDC price straight from the
// Uniswap v3 pool on Base Sepolia (slot0 + pool token balances), server-side,
// so any origin can consume it without the RPC's CORS/UA restrictions. Returns
// USDC-per-wMORM (== USD-per-MORM at the 1:1 wMORM<->MORM mirror). Read-only,
// so CORS is open ("*") and the CDN caches it briefly.

// ★Base mainnet（2026-08 本番プール）。旧 testnet 既定値から更新。
const RPC   = process.env.MORM_RPC          || 'https://mainnet.base.org';
const POOL  = process.env.MORM_POOL_ADDR    || '0x6615fC0239eDDb27A8fF2D774C438e68C4599A55';
const WMORM = process.env.MORM_WMORM_ADDR   || '0x7fEf327a811e73F06cccF0De9db022e739d5076d';
const USDC  = process.env.MORM_USDC_ADDR    || '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const INITIAL_RATE = 0.01; // issuance reference; market floats around it

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};

let _id = 1;
async function rpc(method, params) {
  const r = await fetch(RPC, {
    method: 'POST',
    // a browser-ish UA: the public Base RPC 403s some default agents.
    headers: { 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0', 'Accept': '*/*' },
    body: JSON.stringify({ jsonrpc: '2.0', id: _id++, method, params }),
    cache: 'no-store',
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || 'rpc error');
  return j.result;
}

// ★mainnet プールは wMORM(18 dec)=token0, USDC(6 dec)=token1 → USDC per wMORM = praw*1e12
function priceFromSqrt(sqrtHex) {
  const sqrt = BigInt(sqrtHex);
  const r = Number(sqrt) / 2 ** 96;
  return (r * r) * 1e12;
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS });
}

export async function GET() {
  try {
    const balOf = (token) => rpc('eth_call', [{ to: token, data: '0x70a08231000000000000000000000000' + POOL.slice(2) }, 'latest']);
    const [s0, rw, ru] = await Promise.all([
      rpc('eth_call', [{ to: POOL, data: '0x3850c7bd' }, 'latest']), // slot0()
      balOf(WMORM),
      balOf(USDC),
    ]);
    const price = priceFromSqrt('0x' + s0.slice(2, 66)); // slot0 word0 = sqrtPriceX96
    const wmorm = Number(BigInt(rw)) / 1e18;
    const usdc  = Number(BigInt(ru)) / 1e6;
    const body = {
      ok: true,
      pair: 'wMORM/USDC',
      chain: 'base',
      usdPerMorm: price,      // USD per 1 MORM (via wMORM mirror)
      price,                  // alias
      pool: POOL,
      reserves: { wmorm, usdc },
      tvlUsd: usdc + wmorm * price,
      initialRate: INITIAL_RATE,
      source: 'uniswap-v3-slot0',
      updatedAt: Date.now(),
    };
    return NextResponse.json(body, {
      headers: { ...CORS, 'Cache-Control': 'public, s-maxage=15, stale-while-revalidate=30' },
    });
  } catch (err) {
    // Always return a usable number so consumers can still render.
    return NextResponse.json({
      ok: false,
      pair: 'wMORM/USDC',
      chain: 'base',
      usdPerMorm: INITIAL_RATE,
      price: INITIAL_RATE,
      pool: POOL,
      initialRate: INITIAL_RATE,
      source: 'fallback-initial-rate',
      error: err.message,
      updatedAt: Date.now(),
    }, { status: 200, headers: { ...CORS, 'Cache-Control': 'no-store' } });
  }
}

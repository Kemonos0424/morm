import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// Public price oracle: reads the live wMORM/USDC price straight from the
// Uniswap v3 pool on Base Sepolia (slot0 + pool token balances), server-side,
// so any origin can consume it without the RPC's CORS/UA restrictions. Returns
// USDC-per-wMORM (== USD-per-MORM at the 1:1 wMORM<->MORM mirror). Read-only,
// so CORS is open ("*") and the CDN caches it briefly.

const RPC   = process.env.BASE_SEPOLIA_RPC || 'https://sepolia.base.org';
const POOL  = process.env.MORM_POOL_ADDR   || '0x9E62498516742EC84F3BC71cDB7b2a172dfA5789';
const WMORM = process.env.MORM_WMORM_ADDR  || '0x5cd8053c2fb44a3107109A22dD8529F67751c74C';
const USDC  = process.env.MORM_USDC_ADDR   || '0x2B6648CD0c0bd8e1e50AdCB0F154692a0F90f453';
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

// USDC(6 dec)=token0, wMORM(18 dec)=token1 → USDC per wMORM = (1e18/priceRaw)/1e6
function priceFromSqrt(sqrtHex) {
  const sqrt = BigInt(sqrtHex);
  const r = Number(sqrt) / 2 ** 96;
  return (1e18 / (r * r)) / 1e6;
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
      chain: 'base-sepolia',
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
      chain: 'base-sepolia',
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

// CORS for the public wallet API: the wallet UI is served from the apex site
// (www.morm.one) while these routes live on the dashboard origin, so browser
// fetches are cross-origin. Allow the MORM apex + local dev; echo the request
// origin only when it is on the allowlist.
const ALLOWED = [
  'https://morm.one',
  'https://www.morm.one',
  'http://localhost:8791',
  'http://localhost:3000',
  'http://127.0.0.1:8791',
];

export function corsHeaders(origin) {
  const allow = ALLOWED.includes(origin) ? origin : 'https://morm.one';
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

// Preflight response.
export function preflight(request) {
  return new Response(null, { status: 204, headers: corsHeaders(request.headers.get('origin')) });
}

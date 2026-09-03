// Pinned endpoints. NEVER take these from a page/query param — a wallet must
// not be redirected to an attacker's RPC. Matches manifest host_permissions.
export const API_BASE = "https://api.morm.one";
// Node roster/rewards live on the node dashboard (separate app + DB).
export const NODE_BASE = "https://node.morm.one";

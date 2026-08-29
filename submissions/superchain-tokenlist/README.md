# Superchain Token List submission — wMORM (Base)

Ready-to-submit assets for adding **wMORM** to the Optimism/Superchain token list
(the list Base uses): https://github.com/ethereum-optimism/ethereum-optimism.github.io

## Files (drop into the upstream repo at `data/wMORM/`)

- `data/wMORM/data.json` — token metadata (schema-matched to upstream `data/USDC/data.json`)
- `data/wMORM/logo.svg`  — pure-vector, square 256×256, no fonts / no external refs / no `<image>`

## Verified facts

| field | value | how verified |
|---|---|---|
| chain | Base mainnet (chainId 8453) | `.mainnet-deploy.env` |
| address | `0x7fEf327a811e73F06cccF0De9db022e739d5076d` | deploy env; **EIP-55 checksum MATCH** |
| name | `Wrapped MORM` | `morm-chain/src/WMORM.sol:15` |
| symbol | `wMORM` | `morm-chain/src/WMORM.sol:16` |
| decimals | `18` | `morm-chain/src/WMORM.sol:17` |
| website | `https://morm.one` | site source |

`nobridge: true` is set because wMORM is minted by the custom MORM export bridge
(3-of-5 multisig), not the OP Standard Bridge, and has no canonical L1 ERC-20 on a
listed superchain, so only the `base` entry is provided.

## Submit (PR)

```bash
# 1. fork + clone upstream
gh repo fork ethereum-optimism/ethereum-optimism.github.io --clone
cd ethereum-optimism.github.io

# 2. copy the prepared folder in
mkdir -p data/wMORM
cp /Users/akihisayachida/Desktop/MORM/submissions/superchain-tokenlist/data/wMORM/data.json data/wMORM/
cp /Users/akihisayachida/Desktop/MORM/submissions/superchain-tokenlist/data/wMORM/logo.svg  data/wMORM/

# 3. (optional) run their local validator before pushing
pnpm install && pnpm validate --datadir ./data --tokens wMORM   # see upstream README for exact script name

# 4. branch, commit, PR
git checkout -b add-wMORM
git add data/wMORM
git commit -m "Add wMORM (Base)"
git push -u origin add-wMORM
gh pr create --repo ethereum-optimism/ethereum-optimism.github.io \
  --title "Add wMORM (Base)" \
  --body "Adds Wrapped MORM (wMORM) on Base mainnet. Address 0x7fEf327a811e73F06cccF0De9db022e739d5076d, decimals 18. Pure-vector logo.svg (256×256, square)."
```

## Pre-flight checklist (upstream CI will re-check these)

- [x] `data.json` valid JSON, schema matches upstream example
- [x] address is EIP-55 checksummed
- [x] on-chain `symbol()` == `wMORM`, `decimals()` == 18 (CI calls the contract — must match)
- [x] `logo.svg` square (viewBox 0 0 256 256, width/height 256), vector only, no `<image>`
- [ ] verify the exact validator command + any folder-name casing rule in the **current** upstream README before opening the PR (their CI script names change)

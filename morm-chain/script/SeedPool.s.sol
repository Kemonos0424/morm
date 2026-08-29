// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";

interface IERC20 {
    function approve(address, uint256) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

interface INPM {
    function createAndInitializePoolIfNecessary(
        address token0, address token1, uint24 fee, uint160 sqrtPriceX96
    ) external payable returns (address pool);

    struct MintParams {
        address token0; address token1; uint24 fee;
        int24 tickLower; int24 tickUpper;
        uint256 amount0Desired; uint256 amount1Desired;
        uint256 amount0Min; uint256 amount1Min;
        address recipient; uint256 deadline;
    }
    function mint(MintParams calldata p) external payable
        returns (uint256 tokenId, uint128 liquidity, uint256 amount0, uint256 amount1);
}

/// Seeds a wMORM/USDC Uniswap v3 pool on Base Sepolia at 1 wMORM = 0.01 USDC
/// (full-range liquidity). Env: DEPLOYER_PK, WMORM_ADDR, USDC_ADDR, NPM_ADDR.
contract SeedPool is Script {
    // Base Sepolia Uniswap v3 NonfungiblePositionManager
    address constant NPM_DEFAULT = 0x27F971cb582BF9E50F397e4d29a5C7A34f11faA2;
    uint24  constant FEE = 3000;            // 0.3% (tickSpacing 60)
    int24   constant TL = -887220;          // full range aligned to spacing 60
    int24   constant TU =  887220;

    function run() external {
        uint256 pk    = vm.envUint("DEPLOYER_PK");
        address wmorm = vm.envAddress("WMORM_ADDR");
        address usdc  = vm.envAddress("USDC_ADDR");
        address npmA  = vm.envOr("NPM_ADDR", NPM_DEFAULT);

        // token0 = lower address (USDC 0x2B.. < wMORM 0x5c.. here). price =
        // token1/token0 raw. 1 wMORM = 0.01 USDC <=> raw 1e14; sqrt=1e7.
        (address t0, address t1) = usdc < wmorm ? (usdc, wmorm) : (wmorm, usdc);

        vm.startBroadcast(pk);
        IERC20(usdc).approve(npmA, type(uint256).max);
        IERC20(wmorm).approve(npmA, type(uint256).max);
        address pool = INPM(npmA).createAndInitializePoolIfNecessary(
            t0, t1, FEE, uint160(uint256(1e7) * (2 ** 96)));
        _mint(npmA, t0, t1, vm.addr(pk));
        vm.stopBroadcast();
        console2.log("pool     :", pool);
        console2.log("token0   :", t0);
        console2.log("token1   :", t1);
    }

    function _mint(address npmA, address t0, address t1, address to) internal {
        // 1,000 USDC + 100,000 wMORM (balanced at 0.01 USDC/wMORM)
        (uint256 a0, uint256 a1) =
            t0 < t1 && _is6dec(t0) ? (uint256(1_000 * 1e6), uint256(100_000 * 1e18))
                                    : (uint256(100_000 * 1e18), uint256(1_000 * 1e6));
        (uint256 id, uint128 liq,,) = INPM(npmA).mint(INPM.MintParams({
            token0: t0, token1: t1, fee: FEE, tickLower: TL, tickUpper: TU,
            amount0Desired: a0, amount1Desired: a1, amount0Min: 0, amount1Min: 0,
            recipient: to, deadline: block.timestamp + 3600
        }));
        console2.log("tokenId  :", id);
        console2.log("liquidity:", uint256(liq));
    }

    function _is6dec(address t) internal view returns (bool) {
        (bool ok, bytes memory d) = t.staticcall(abi.encodeWithSignature("decimals()"));
        return ok && abi.decode(d, (uint8)) == 6;
    }
}

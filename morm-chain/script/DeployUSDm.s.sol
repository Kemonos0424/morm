// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {USDm} from "../src/USDm.sol";

/// @notice Deploys USDm (USDC-backed 1:1 wrapper) on Base mainnet.
///   env: DEPLOYER_PK, USDC_ADDR (Base native USDC 0x833589…).
///   forge script script/DeployUSDm.s.sol --rpc-url "$RPC_URL" --broadcast --verify
contract DeployUSDm is Script {
    // Base mainnet native Circle USDC (fallback if USDC_ADDR unset).
    address constant USDC_MAINNET = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;

    function run() external {
        uint256 pk   = vm.envUint("DEPLOYER_PK");
        address usdc = vm.envOr("USDC_ADDR", USDC_MAINNET);
        require(usdc != address(0), "USDC_ADDR unset");
        vm.startBroadcast(pk);
        USDm t = new USDm(usdc);
        vm.stopBroadcast();
        console2.log("USDm     :", address(t));
        console2.log("backedBy :", usdc);
        console2.log("decimals :", t.decimals());
    }
}

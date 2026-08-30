// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {USDmLockBridge} from "../src/USDmLockBridge.sol";

/// @notice Deploys USDmLockBridge (escrow bridge for USDm ↔ MORM L1) on Base mainnet.
///   Reuses the same env as the wMORM bridge: SIGNERS (comma-list), THRESHOLD,
///   GUARDIAN, WINDOW_LEN. Adds USDM_ADDR, USDM_MAX_UNLOCK_PER_WINDOW, USDM_MIN_LOCK.
///   forge script script/DeployUSDmLockBridge.s.sol --rpc-url "$RPC_URL" --broadcast
contract DeployUSDmLockBridge is Script {
    function run() external {
        uint256 pk       = vm.envUint("DEPLOYER_PK");
        address usdm     = vm.envAddress("USDM_ADDR");
        address guardian = vm.envAddress("GUARDIAN");
        uint256 threshold= vm.envOr("THRESHOLD", uint256(3));
        uint256 windowLen= vm.envOr("WINDOW_LEN", uint256(3600));
        // USDm has 6 decimals: 1e12 = 1,000,000 USDm/window; minLock 0 = no floor.
        uint256 maxUnlock= vm.envOr("USDM_MAX_UNLOCK_PER_WINDOW", uint256(1_000_000_000_000));
        uint256 minLock  = vm.envOr("USDM_MIN_LOCK", uint256(0));

        address[] memory legacy = new address[](3);
        legacy[0] = vm.envOr("SIGNER_A", vm.addr(0xA11CE));
        legacy[1] = vm.envOr("SIGNER_B", vm.addr(0xB0B));
        legacy[2] = vm.envOr("SIGNER_C", vm.addr(0xC0C));
        address[] memory signers = vm.envOr("SIGNERS", ",", legacy);
        require(signers.length >= threshold && threshold > 0, "bad threshold/signers");

        vm.startBroadcast(pk);
        USDmLockBridge b = new USDmLockBridge(
            usdm, signers, threshold, guardian, windowLen, maxUnlock, minLock);
        vm.stopBroadcast();

        console2.log("USDmLockBridge :", address(b));
        console2.log("token(USDm)    :", usdm);
        console2.log("signerCount    :", b.signerCount());
        console2.log("threshold      :", threshold);
        console2.log("guardian       :", guardian);
        console2.log("maxUnlock/win  :", maxUnlock);
    }
}

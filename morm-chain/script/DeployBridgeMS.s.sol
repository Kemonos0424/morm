// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MORMBridgeMS} from "../src/MORMBridgeMS.sol";

/// @notice Phase 13b PoC deploy: 3 anvil keys (#5, #6, #7) as signers,
///         threshold = 2. Anyone can lock; unlock requires 2-of-3.
contract DeployBridgeMS is Script {
    function run() external {
        uint256 deployerKey = vm.envOr("DEPLOYER_PK",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        // anvil deterministic accts #5 #6 #7 (independent from #1 used as
        // the legacy single relayer / treasury EVM addr in Phase 12 PoC).
        // Sorted ascending by address as the constructor requires.
        address s1 = 0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc; // #5
        address s2 = 0x976EA74026E726554dB657fA54763abd0C3a0aa9; // #6
        address s3 = 0x14dC79964da2C08b23698B3D3cc7Ca32193d9955; // #7

        // Sort ascending (constructor enforces no duplicates and the
        // unlock loop requires ascending input order; sorting at deploy
        // time also matches ascending iteration in the relayer).
        address[3] memory tmp = [s1, s2, s3];
        for (uint256 i; i < 3; ++i) {
            for (uint256 j = i + 1; j < 3; ++j) {
                if (tmp[j] < tmp[i]) {
                    address t = tmp[i]; tmp[i] = tmp[j]; tmp[j] = t;
                }
            }
        }
        address[] memory signers = new address[](3);
        signers[0] = tmp[0]; signers[1] = tmp[1]; signers[2] = tmp[2];

        vm.startBroadcast(deployerKey);
        MORMBridgeMS bridge = new MORMBridgeMS(signers, 2);
        vm.stopBroadcast();

        console2.log("MORMBridgeMS deployed at:", address(bridge));
        console2.log("signer[0]:", signers[0]);
        console2.log("signer[1]:", signers[1]);
        console2.log("signer[2]:", signers[2]);
        console2.log("threshold: 2 of 3");
    }
}

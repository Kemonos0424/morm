// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MORMEscrow} from "../src/MORMEscrow.sol";

contract Deploy is Script {
    function run() external {
        // anvil default account #0 deploys; treasury = anvil account #1
        uint256 deployerKey = vm.envOr("DEPLOYER_PK",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        address treasury = vm.envOr("TREASURY",
            address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));

        vm.startBroadcast(deployerKey);
        MORMEscrow esc = new MORMEscrow(treasury);
        vm.stopBroadcast();

        console2.log("MORMEscrow deployed at:", address(esc));
        console2.log("treasury (collects 1% fee):", treasury);
    }
}

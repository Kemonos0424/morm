// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MORMBridge} from "../src/MORMBridge.sol";

contract DeployBridge is Script {
    function run() external {
        uint256 deployerKey = vm.envOr("DEPLOYER_PK",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        address treasury = vm.envOr("TREASURY",
            address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));

        vm.startBroadcast(deployerKey);
        MORMBridge bridge = new MORMBridge(treasury);
        vm.stopBroadcast();

        console2.log("MORMBridge deployed at:", address(bridge));
        console2.log("treasury (relayer):", treasury);
    }
}

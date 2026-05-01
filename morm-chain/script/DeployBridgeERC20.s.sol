// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {MORMBridgeERC20} from "../src/MORMBridgeERC20.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

contract DeployBridgeERC20 is Script {
    function run() external {
        uint256 deployerKey = vm.envOr("DEPLOYER_PK",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        address treasury = vm.envOr("TREASURY",
            address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));

        vm.startBroadcast(deployerKey);
        MockUSDC usdc = new MockUSDC();
        MORMBridgeERC20 bridge = new MORMBridgeERC20(treasury);
        // mint 10K USDC to the deployer for the demo
        usdc.mint(vm.addr(deployerKey), 10_000 * 1e6);
        vm.stopBroadcast();

        console2.log("MockUSDC deployed at:", address(usdc));
        console2.log("MORMBridgeERC20 deployed at:", address(bridge));
    }
}

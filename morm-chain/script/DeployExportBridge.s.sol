// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {WMORM} from "../src/WMORM.sol";
import {MORMExportBridge} from "../src/MORMExportBridge.sol";
import {MockUSDC} from "../src/MockUSDC.sol";

/// @notice Deploys the wMORM export stack (WMORM + MORMExportBridge, wired),
///         plus an optional MockUSDC for a testnet wMORM/USDC pool.
///
///  Base Sepolia:
///    forge script script/DeployExportBridge.s.sol \
///      --rpc-url $BASE_SEPOLIA_RPC --broadcast --verify
///
///  Env (all optional; defaults are local-sim only — set real values on Base):
///    DEPLOYER_PK, GUARDIAN, SIGNER_A/B/C, THRESHOLD,
///    WINDOW_LEN, MAX_MINT_PER_WINDOW, MAX_SUPPLY, MIN_EXIT, DEPLOY_MOCK_USDC
contract DeployExportBridge is Script {
    struct Cfg {
        uint256 pk;
        address guardian;
        address[] signers;
        uint256 threshold;
        uint256 windowLen;
        uint256 maxWin;
        uint256 maxSupply;
        uint256 minExit;
        bool deployUsdc;
    }

    function _cfg() internal view returns (Cfg memory c) {
        c.pk = vm.envOr("DEPLOYER_PK",
            uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80)); // anvil #0
        c.guardian = vm.envOr("GUARDIAN",
            address(0x70997970C51812dc3A010C7d01b50e0d17dc79C8));                        // anvil #1
        c.signers = new address[](3);
        c.signers[0] = vm.envOr("SIGNER_A", vm.addr(0xA11CE));
        c.signers[1] = vm.envOr("SIGNER_B", vm.addr(0xB0B));
        c.signers[2] = vm.envOr("SIGNER_C", vm.addr(0xC0C));
        c.threshold = vm.envOr("THRESHOLD", uint256(2));
        c.windowLen = vm.envOr("WINDOW_LEN", uint256(1 hours));
        c.maxWin    = vm.envOr("MAX_MINT_PER_WINDOW", uint256(1_000_000 ether));
        c.maxSupply = vm.envOr("MAX_SUPPLY", uint256(100_000_000 ether));
        c.minExit   = vm.envOr("MIN_EXIT", uint256(0));
        c.deployUsdc = vm.envOr("DEPLOY_MOCK_USDC", true);
    }

    function run() external {
        Cfg memory c = _cfg();
        vm.startBroadcast(c.pk);
        WMORM w = new WMORM();
        MORMExportBridge b = new MORMExportBridge(
            address(w), c.signers, c.threshold, c.guardian,
            c.windowLen, c.maxWin, c.maxSupply, c.minExit);
        w.setBridge(address(b));
        address usdc;
        if (c.deployUsdc) {
            MockUSDC u = new MockUSDC();
            u.mint(vm.addr(c.pk), 1_000_000e6);   // seed for a wMORM/USDC test pool
            usdc = address(u);
        }
        vm.stopBroadcast();

        console2.log("WMORM            :", address(w));
        console2.log("MORMExportBridge :", address(b));
        console2.log("MockUSDC         :", usdc);
        console2.log("guardian         :", c.guardian);
        console2.log("threshold        :", c.threshold);
    }
}

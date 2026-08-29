// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";

interface IERC20 { function approve(address, uint256) external returns (bool); }

interface ISwapRouter02 {
    struct ExactInputSingleParams {
        address tokenIn; address tokenOut; uint24 fee; address recipient;
        uint256 amountIn; uint256 amountOutMinimum; uint160 sqrtPriceLimitX96;
    }
    function exactInputSingle(ExactInputSingleParams calldata p) external payable returns (uint256);
}

/// Buys wMORM with USDC on the Base Sepolia pool to move the price (demo/trade
/// history). Env: DEPLOYER_PK, WMORM_ADDR, USDC_ADDR, AMOUNT_USDC (6dec units).
contract SwapTest is Script {
    address constant ROUTER = 0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4; // SwapRouter02
    uint24  constant FEE = 3000;

    function run() external {
        uint256 pk    = vm.envUint("DEPLOYER_PK");
        address wmorm = vm.envAddress("WMORM_ADDR");
        address usdc  = vm.envAddress("USDC_ADDR");
        bool sell     = vm.envOr("SELL", false);          // 1 = sell wMORM for USDC
        uint256 amtIn = vm.envUint("AMOUNT_IN");          // raw units of tokenIn
        (address tin, address tout) = sell ? (wmorm, usdc) : (usdc, wmorm);

        vm.startBroadcast(pk);
        IERC20(tin).approve(ROUTER, amtIn);
        uint256 out = ISwapRouter02(ROUTER).exactInputSingle(ISwapRouter02.ExactInputSingleParams({
            tokenIn: tin, tokenOut: tout, fee: FEE, recipient: vm.addr(pk),
            amountIn: amtIn, amountOutMinimum: 0, sqrtPriceLimitX96: 0
        }));
        vm.stopBroadcast();
        console2.log("sell?           :", sell);
        console2.log("amountIn        :", amtIn);
        console2.log("amountOut       :", out);
    }
}

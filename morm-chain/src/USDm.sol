// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title USDm — a fully USDC-backed 1:1 USD token for the MORM ecosystem.
/// @notice Trustless wrapper: deposit USDC → mint USDm 1:1; burn USDm → withdraw
///         USDC 1:1. There is NO admin, NO owner, NO mint authority beyond a
///         matching USDC deposit, so `totalSupply` is always fully backed by the
///         USDC this contract holds (direct USDC donations only ADD backing).
///         Same 6 decimals as USDC ⇒ 1 USDm-unit == 1 USDC-unit, no scaling.
///
///         Peg model: USDm is NOT algorithmic and NOT MORM-collateralised. Its
///         value comes solely from redeemable USDC reserves — the safe design.
///
///         ★ Value-holding stablecoin: BEFORE mainnet use with real funds, have
///         this audited and confirm the compliance stance (a regulated issuer
///         may need a blocklist/pause — deliberately omitted here to keep v1
///         trustless; add in a reviewed v2 if required). Dependency-free to match
///         this repo's style and stay auditable.
interface IERC20 {
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

contract USDm {
    string public constant name = "MORM USD";
    string public constant symbol = "USDm";
    uint8  public constant decimals = 6;                 // == USDC, exact 1:1

    IERC20 public immutable usdc;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Deposit(address indexed from, address indexed to, uint256 amount);
    event Withdraw(address indexed from, address indexed to, uint256 amount);

    error ZeroAddress();
    error InsufficientBalance();
    error InsufficientAllowance();
    error TransferFailed();

    constructor(address _usdc) {
        if (_usdc == address(0)) revert ZeroAddress();
        usdc = IERC20(_usdc);
    }

    // --- mint against USDC deposit (1:1) ---
    function deposit(uint256 amount) external returns (uint256) {
        return depositTo(msg.sender, amount);
    }

    /// @notice Pull `amount` USDC from the caller and mint the actually-received
    ///         USDC amount as USDm to `to` (balance-delta ⇒ safe even if USDC
    ///         ever became fee-on-transfer; it is not today).
    function depositTo(address to, uint256 amount) public returns (uint256 minted) {
        if (to == address(0)) revert ZeroAddress();
        uint256 pre = usdc.balanceOf(address(this));
        _pull(usdc, msg.sender, amount);
        minted = usdc.balanceOf(address(this)) - pre;    // actual received
        totalSupply += minted;
        unchecked { balanceOf[to] += minted; }
        emit Transfer(address(0), to, minted);
        emit Deposit(msg.sender, to, minted);
    }

    // --- burn to redeem USDC (1:1) ---
    function withdraw(uint256 amount) external {
        withdrawTo(msg.sender, amount);
    }

    /// @notice Burn `amount` USDm from the caller and send `amount` USDC to `to`.
    ///         Effects (burn) precede the interaction (USDC transfer).
    function withdrawTo(address to, uint256 amount) public {
        if (to == address(0)) revert ZeroAddress();
        uint256 b = balanceOf[msg.sender];
        if (b < amount) revert InsufficientBalance();
        unchecked {
            balanceOf[msg.sender] = b - amount;
            totalSupply -= amount;
        }
        emit Transfer(msg.sender, address(0), amount);
        emit Withdraw(msg.sender, to, amount);
        _push(usdc, to, amount);
    }

    // --- ERC-20 ---
    function transfer(address to, uint256 value) external returns (bool) {
        return _transfer(msg.sender, to, value);
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        if (a < value) revert InsufficientAllowance();
        if (a != type(uint256).max) allowance[from][msg.sender] = a - value;
        return _transfer(from, to, value);
    }

    function _transfer(address from, address to, uint256 value) internal returns (bool) {
        if (to == address(0)) revert ZeroAddress();
        uint256 b = balanceOf[from];
        if (b < value) revert InsufficientBalance();
        unchecked {
            balanceOf[from] = b - value;
            balanceOf[to] += value;
        }
        emit Transfer(from, to, value);
        return true;
    }

    // --- safe USDC calls (USDC returns bool true; require it) ---
    function _pull(IERC20 t, address from, uint256 amt) internal {
        if (!t.transferFrom(from, address(this), amt)) revert TransferFailed();
    }
    function _push(IERC20 t, address to, uint256 amt) internal {
        if (!t.transfer(to, amt)) revert TransferFailed();
    }

    /// @notice Backing invariant helper: USDC held ≥ USDm outstanding (always true).
    function backing() external view returns (uint256 usdcHeld, uint256 outstanding) {
        return (usdc.balanceOf(address(this)), totalSupply);
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title MORM Escrow + Registry + Node-Lock
/// @notice Single contract embodying MORM.md §4 (Tokenomics: 1% fee),
///         §5 (Generation-ID & content registry), §6 (Proof of Physical
///         Evidence + Slash). Kept intentionally compact for the PoC —
///         production splits this into modules and replaces `treasury`
///         with a DAO/AI-validator multisig.
contract MORMEscrow {
    address public immutable treasury;
    uint16 public constant FEE_BPS = 100;          // 100/10000 = 1.0%
    uint16 private constant BPS_DENOM = 10000;

    enum OrderStatus {
        None,
        Created,
        PackingProofSubmitted,
        OpeningProofSubmitted,
        Finalized,
        Refunded
    }

    struct Content {
        bytes32 rootHash;
        bytes32 generationId;
        address creator;
        uint64 registeredAt;
    }

    struct Order {
        bytes32 contentId;
        address buyer;
        address seller;
        uint256 amount;       // 99% in escrow
        uint256 fee;          // 1% already paid to treasury
        bytes32 packingHash;
        bytes32 openingHash;
        OrderStatus status;
        uint64 createdAt;
    }

    mapping(bytes32 => Content) public contents;          // contentId
    mapping(bytes32 => bytes32) public generationIds;     // generationId → contentId
    mapping(bytes32 => Order)   public orders;            // orderId
    mapping(address => bool)    public nodeLocked;        // permanent ban
    mapping(address => uint256) public stakeOf;           // node stake balance

    event ContentRegistered(bytes32 indexed contentId, bytes32 rootHash, bytes32 generationId, address creator);
    event OrderCreated(bytes32 indexed orderId, bytes32 contentId, address buyer, address seller, uint256 amount, uint256 fee);
    event PackingProofSubmitted(bytes32 indexed orderId, bytes32 packingHash);
    event OpeningProofSubmitted(bytes32 indexed orderId, bytes32 openingHash);
    event OrderFinalized(bytes32 indexed orderId, bool valid);
    event NodeLocked(address indexed node, uint256 slashedAmount);
    event Staked(address indexed node, uint256 amount);
    event Unstaked(address indexed node, uint256 amount);

    error AlreadyRegistered();
    error GenerationCollision();
    error OrderExists();
    error UnknownContent();
    error NotBuyer();
    error NotSeller();
    error WrongStatus();
    error NodeIsLocked();
    error NotTreasury();
    error TransferFailed();
    error ZeroAddress();
    error InsufficientStake();

    modifier onlyTreasury() {
        if (msg.sender != treasury) revert NotTreasury();
        _;
    }

    constructor(address _treasury) {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = _treasury;
    }

    // -- Registry ---------------------------------------------------------

    function registerContent(
        bytes32 contentId,
        bytes32 rootHash,
        bytes32 generationId
    ) external {
        if (nodeLocked[msg.sender]) revert NodeIsLocked();
        if (contents[contentId].creator != address(0)) revert AlreadyRegistered();
        if (generationId != bytes32(0)) {
            if (generationIds[generationId] != bytes32(0)) revert GenerationCollision();
            generationIds[generationId] = contentId;
        }
        contents[contentId] = Content({
            rootHash: rootHash,
            generationId: generationId,
            creator: msg.sender,
            registeredAt: uint64(block.timestamp)
        });
        emit ContentRegistered(contentId, rootHash, generationId, msg.sender);
    }

    // -- Orders -----------------------------------------------------------

    function createOrder(
        bytes32 orderId,
        bytes32 contentId,
        address seller
    ) external payable {
        if (orders[orderId].status != OrderStatus.None) revert OrderExists();
        if (nodeLocked[msg.sender] || nodeLocked[seller]) revert NodeIsLocked();
        if (contents[contentId].creator == address(0)) revert UnknownContent();
        if (seller == address(0)) revert ZeroAddress();

        uint256 fee = (msg.value * FEE_BPS) / BPS_DENOM;
        uint256 amt = msg.value - fee;

        // Phase 26f — Check-Effect-Interact: write the order BEFORE the
        // external call to `treasury`. A malicious treasury contract
        // re-entering createOrder during the call would otherwise see
        // `orders[orderId].status == None` and could create a duplicate
        // entry, draining buyer funds twice. With the order written
        // first, the second entry hits OrderExists and reverts, and a
        // failed treasury transfer rolls back the entire tx (including
        // this write).
        orders[orderId] = Order({
            contentId: contentId,
            buyer: msg.sender,
            seller: seller,
            amount: amt,
            fee: fee,
            packingHash: bytes32(0),
            openingHash: bytes32(0),
            status: OrderStatus.Created,
            createdAt: uint64(block.timestamp)
        });

        (bool ok, ) = treasury.call{value: fee}("");
        if (!ok) revert TransferFailed();

        emit OrderCreated(orderId, contentId, msg.sender, seller, amt, fee);
    }

    function submitPackingProof(bytes32 orderId, bytes32 packingHash) external {
        Order storage o = orders[orderId];
        if (msg.sender != o.seller) revert NotSeller();
        if (o.status != OrderStatus.Created) revert WrongStatus();
        o.packingHash = packingHash;
        o.status = OrderStatus.PackingProofSubmitted;
        emit PackingProofSubmitted(orderId, packingHash);
    }

    function submitOpeningProof(bytes32 orderId, bytes32 openingHash) external {
        Order storage o = orders[orderId];
        if (msg.sender != o.buyer) revert NotBuyer();
        if (o.status != OrderStatus.PackingProofSubmitted) revert WrongStatus();
        o.openingHash = openingHash;
        o.status = OrderStatus.OpeningProofSubmitted;
        emit OpeningProofSubmitted(orderId, openingHash);
    }

    /// @notice In production this is called by a DAO/AI-validator after
    ///         analyzing the packing+opening videos for tampering.
    function finalize(bytes32 orderId, bool valid) external onlyTreasury {
        Order storage o = orders[orderId];
        if (o.status != OrderStatus.OpeningProofSubmitted) revert WrongStatus();

        if (valid) {
            o.status = OrderStatus.Finalized;
            (bool ok, ) = o.seller.call{value: o.amount}("");
            if (!ok) revert TransferFailed();
        } else {
            o.status = OrderStatus.Refunded;
            (bool ok, ) = o.buyer.call{value: o.amount}("");
            if (!ok) revert TransferFailed();

            uint256 slashed = stakeOf[o.seller];
            stakeOf[o.seller] = 0;
            nodeLocked[o.seller] = true;
            if (slashed > 0) {
                (bool ok2, ) = treasury.call{value: slashed}("");
                if (!ok2) revert TransferFailed();
            }
            emit NodeLocked(o.seller, slashed);
        }
        emit OrderFinalized(orderId, valid);
    }

    // -- Node staking -----------------------------------------------------

    function stakeNode() external payable {
        if (nodeLocked[msg.sender]) revert NodeIsLocked();
        stakeOf[msg.sender] += msg.value;
        emit Staked(msg.sender, msg.value);
    }

    function unstakeNode(uint256 amount) external {
        if (nodeLocked[msg.sender]) revert NodeIsLocked();
        if (stakeOf[msg.sender] < amount) revert InsufficientStake();
        stakeOf[msg.sender] -= amount;
        (bool ok, ) = msg.sender.call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Unstaked(msg.sender, amount);
    }
}

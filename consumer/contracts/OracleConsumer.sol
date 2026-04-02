// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title OracleConsumer
 * @dev EVM contract that integrates with GenLayer Oracle Hub for prediction markets
 * Receives AI-powered verdicts from GenLayer and distributes winnings
 */
contract OracleConsumer {
    // Market states (must match GenLayer hub)
    enum MarketState {
        PENDING,    // Created, accepting bets
        RESOLVING,  // AI jury active
        RESOLVED    // Verdict received
    }

    // Market outcomes
    enum Outcome {
        UNRESOLVED, // Default state
        YES,        // Positive outcome
        NO,         // Negative outcome
        INVALID     // Market cancelled/invalid
    }

    // Market structure
    struct Market {
        string question;
        MarketState state;
        Outcome outcome;
        uint256 yesPool;
        uint256 noPool;
        uint256 deadline;
        uint256 confidence;      // AI confidence score (0-1000)
        bool verdictReceived;
        string reasoning;        // AI reasoning for verdict
        uint256 totalPool;
    }

    // Separate mappings for bets (can't have mappings in public structs)
    mapping(string => mapping(address => uint256)) public yesBets;
    mapping(string => mapping(address => uint256)) public noBets;

    // Events
    event MarketCreated(string indexed marketId, string question, uint256 deadline);
    event BetPlaced(string indexed marketId, address indexed bettor, bool isYes, uint256 amount);
    event VerdictReceived(string indexed marketId, Outcome outcome, uint256 confidence, string reasoning);
    event WinningsClaimed(string indexed marketId, address indexed claimer, uint256 amount);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // State variables
    mapping(string => Market) public markets;
    string[] public marketIds;

    // Configuration
    address public owner;
    address public relayer;           // Authorized relayer address
    string public chainKey;           // Chain identifier for GenLayer hub
    uint256 public oracleFee;         // Fee for oracle services (wei)

    // Reentrancy guard
    bool private _locked;

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier nonReentrant() {
        require(!_locked, "Reentrant call");
        _locked = true;
        _;
        _locked = false;
    }

    /**
     * @dev Constructor
     * @param _relayer Authorized relayer address (can be zero address for open relay)
     * @param _chainKey Chain identifier for GenLayer hub registration
     * @param _oracleFee Fee charged for oracle services
     */
    constructor(
        address _relayer,
        string memory _chainKey,
        uint256 _oracleFee
    ) {
        owner = msg.sender;
        relayer = msg.sender;
        chainKey = _chainKey;
        oracleFee = _oracleFee;
        _locked = false;
    }

    /**
     * @dev Create a new prediction market
     * @param marketId Unique market identifier
     * @param question The prediction question
     * @param deadline Unix timestamp when betting closes
     */
    function createMarket(
        string memory marketId,
        string memory question,
        uint256 deadline
    ) external onlyOwner {
        require(bytes(marketId).length > 0, "Market ID required");
        require(bytes(question).length > 0, "Question required");
        require(deadline > block.timestamp, "Deadline must be in future");
        require(markets[marketId].deadline == 0, "Market already exists");

        Market storage market = markets[marketId];
        market.question = question;
        market.state = MarketState.PENDING;
        market.outcome = Outcome.UNRESOLVED;
        market.deadline = deadline;
        market.verdictReceived = false;

        marketIds.push(marketId);

        emit MarketCreated(marketId, question, deadline);
    }

    /**
     * @dev Place a bet on a market
     * @param marketId The market to bet on
     * @param isYes True for YES bet, false for NO bet
     */
    function placeBet(string memory marketId, bool isYes) external payable nonReentrant {
        Market storage market = markets[marketId];
        require(market.deadline > 0, "Market does not exist");
        require(market.state == MarketState.PENDING, "Market not accepting bets");
        require(block.timestamp < market.deadline, "Betting period ended");
        require(msg.value > 0, "Bet amount must be > 0");

        if (isYes) {
            yesBets[marketId][msg.sender] += msg.value;
            market.yesPool += msg.value;
        } else {
            noBets[marketId][msg.sender] += msg.value;
            market.noPool += msg.value;
        }

        market.totalPool += msg.value;

        emit BetPlaced(marketId, msg.sender, isYes, msg.value);
    }

    /**
     * @dev Receive verdict from GenLayer Oracle Hub (only callable by relayer)
     * @param marketId The market ID
     * @param outcome The resolved outcome (1=YES, 2=NO, 3=INVALID)
     * @param confidence AI confidence score (0-1000)
     * @param reasoning AI reasoning for the verdict
     */
    function receiveVerdict(
        string memory marketId,
        uint8 outcome,
        uint256 confidence,
        string memory reasoning
    ) external {
        // Allow anyone if relayer is zero address, otherwise only relayer
        if (relayer != address(0)) {
            require(msg.sender == relayer, "Only relayer can call");
        }

        Market storage market = markets[marketId];
        require(market.deadline > 0, "Market does not exist");
        require(market.state != MarketState.RESOLVED, "Market already resolved");
        require(outcome >= 1 && outcome <= 3, "Invalid outcome");

        market.state = MarketState.RESOLVED;
        market.outcome = Outcome(outcome);
        market.confidence = confidence;
        market.reasoning = reasoning;
        market.verdictReceived = true;

        emit VerdictReceived(marketId, market.outcome, confidence, reasoning);
    }

    /**
     * @dev Claim winnings for a resolved market
     * @param marketId The market ID
     */
    function claimWinnings(string memory marketId) external nonReentrant {
        Market storage market = markets[marketId];
        require(market.state == MarketState.RESOLVED, "Market not resolved");
        require(market.outcome != Outcome.UNRESOLVED, "Market unresolved");

        uint256 userBet;
        uint256 winningPool;

        if (market.outcome == Outcome.YES) {
            userBet = yesBets[marketId][msg.sender];
            winningPool = market.yesPool;
            yesBets[marketId][msg.sender] = 0;
        } else if (market.outcome == Outcome.NO) {
            userBet = noBets[marketId][msg.sender];
            winningPool = market.noPool;
            noBets[marketId][msg.sender] = 0;
        } else {
            // INVALID outcome - return all bets
            userBet = yesBets[marketId][msg.sender] + noBets[marketId][msg.sender];
            winningPool = market.totalPool;
            yesBets[marketId][msg.sender] = 0;
            noBets[marketId][msg.sender] = 0;
        }

        require(userBet > 0, "No winnings to claim");

        uint256 winnings;
        if (market.outcome == Outcome.INVALID) {
            // Return original bet amount
            winnings = userBet;
        } else {
            // Proportional winnings from losing pool
            uint256 losingPool = market.totalPool - winningPool;
            winnings = userBet + (userBet * losingPool / winningPool);
        }

        // Transfer winnings
        (bool success,) = payable(msg.sender).call{value: winnings}("");
        require(success, "Transfer failed");

        emit WinningsClaimed(marketId, msg.sender, winnings);
    }

    /**
     * @dev Get market information
     * @param marketId The market ID
     * @return question The market question
     * @return state Current market state
     * @return outcome Resolved outcome
     * @return yesPool Total YES bets
     * @return noPool Total NO bets
     * @return deadline Betting deadline
     * @return confidence AI confidence score
     * @return verdictReceived Whether verdict has been received
     */
    function getMarket(string memory marketId) external view returns (
        string memory question,
        uint8 state,
        uint8 outcome,
        uint256 yesPool,
        uint256 noPool,
        uint256 deadline,
        uint256 confidence,
        bool verdictReceived
    ) {
        Market storage market = markets[marketId];
        return (
            market.question,
            uint8(market.state),
            uint8(market.outcome),
            market.yesPool,
            market.noPool,
            market.deadline,
            market.confidence,
            market.verdictReceived
        );
    }

    /**
     * @dev Get user's bet amounts for a market
     * @param marketId The market ID
     * @param user The user address
     * @return yesBet Amount bet on YES
     * @return noBet Amount bet on NO
     */
    function getUserBets(string memory marketId, address user) external view returns (
        uint256 yesBet,
        uint256 noBet
    ) {
        return (
            yesBets[marketId][user],
            noBets[marketId][user]
        );
    }

    /**
     * @dev Get all market IDs
     * @return Array of market IDs
     */
    function getAllMarkets() external view returns (string[] memory) {
        return marketIds;
    }

    /**
     * @dev Update relayer address (only owner)
     * @param newRelayer New relayer address
     */
    function setRelayer(address newRelayer) external onlyOwner {
        relayer = newRelayer;
    }

    /**
     * @dev Update oracle fee (only owner)
     * @param newFee New oracle fee in wei
     */
    function setOracleFee(uint256 newFee) external onlyOwner {
        oracleFee = newFee;
    }

    /**
     * @dev Withdraw accumulated fees (only owner)
     */
    function withdrawFees() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No fees to withdraw");
        (bool success,) = payable(owner).call{value: balance}("");
        require(success, "Transfer failed");
    }

    /**
     * @dev Transfer ownership
     * @param newOwner New owner address
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "New owner is zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /**
     * @dev Emergency pause market (only owner)
     * @param marketId The market to pause
     */
    function emergencyPause(string memory marketId) external onlyOwner {
        Market storage market = markets[marketId];
        require(market.deadline > 0, "Market does not exist");
        market.state = MarketState.RESOLVED;
        market.outcome = Outcome.INVALID;
        market.verdictReceived = true;
    }
}

   
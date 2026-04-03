from gltest import get_contract_factory, default_account
from gltest.helpers import load_fixture
from gltest.assertions import tx_execution_succeeded


def deploy_contract():
    factory = get_contract_factory("OracleHub")
    contract = factory.deploy(args=[])

    # Register a chain (Polymarket-like)
    register_result = contract.register_chain(args=[
        "polygon-polymarket-v2",  # chain_key
        0,  # chain_type: EVM
        3,  # adapter_type: RELAYER
        "0x1234567890123456789012345678901234567890",  # adapter_address
        "https://api.polymarket.com/callback",  # callback_url
        '{"chain_id": 137, "contract": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045", "market_api_url": "https://gamma-api.polymarket.com/query"}',  # metadata
        200,  # fee_bps (2%)
    ], value=10000000000000000000)  # 10 ETH stake
    assert tx_execution_succeeded(register_result)

    # Create a market
    create_result = contract.create_market(args=[
        "polygon-polymarket-v2",  # chain_key
        "bitcoin-100k-2024",  # external_id
        "Will Bitcoin reach $100,000 by end of 2024?",  # question
        "Bitcoin price prediction market on Polymarket",  # description
        "YES if Bitcoin closes above $100,000 on Dec 31, 2024 UTC. NO otherwise. INVALID if exchange ceases trading.",  # resolution_criteria
        ["https://coinmarketcap.com/currencies/bitcoin/", "https://www.coingecko.com/en/coins/bitcoin"],  # evidence_urls
        1735689600,  # deadline (Dec 31, 2024)
        1000000000000000000000,  # prize_pool_proxy (1000 ETH worth)
    ], value=15000000000000000000)  # 15 ETH fee (1.5% of 1000 ETH)
    assert tx_execution_succeeded(create_result)

    return contract


def test_oracle_hub_basic_functionality():
    """Test basic Oracle Hub functionality: chain registration, market creation."""
    contract = load_fixture(deploy_contract)

    # Check hub stats
    stats = contract.get_hub_stats(args=[])
    assert stats["total_chains"] == 1
    assert stats["total_markets"] == 1
    assert stats["total_fees"] == "15000000000000000000"  # 15 ETH

    # Check chain info
    chain_info = contract.get_chain(args=["polygon-polymarket-v2"])
    assert chain_info["chain_key"] == "polygon-polymarket-v2"
    assert chain_info["active"] == True
    assert chain_info["fee_bps"] == 200
    assert chain_info["markets_created"] == 1

    # Check market info
    market_info = contract.get_market(args=["polygon-polymarket-v2:bitcoin-100k-2024"])
    assert market_info["market_id"] == "polygon-polymarket-v2:bitcoin-100k-2024"
    assert market_info["chain_key"] == "polygon-polymarket-v2"
    assert market_info["external_id"] == "bitcoin-100k-2024"
    assert market_info["question"] == "Will Bitcoin reach $100,000 by end of 2024?"
    assert market_info["state"] == "PENDING"
    assert market_info["outcome"] == "UNRESOLVED"
    assert market_info["fee_charged"] == "15000000000000000000"  # 15 ETH


def test_oracle_hub_resolution():
    """Test market resolution process."""
    contract = load_fixture(deploy_contract)

    market_id = "polygon-polymarket-v2:bitcoin-100k-2024"

    # Trigger resolution (should work since we're the chain owner)
    resolve_result = contract.trigger_resolution(args=[market_id])
    assert tx_execution_succeeded(resolve_result)

    # Check that market is now resolved
    market_info = contract.get_market(args=[market_id])
    assert market_info["state"] == "RESOLVED"
    assert market_info["outcome"] in ["YES", "NO", "INVALID"]
    assert market_info["confidence"] > 0.0
    assert len(market_info["reasoning"]) > 0

    # Check verdict endpoint
    verdict = contract.get_verdict(args=[market_id])
    assert verdict is not None
    assert verdict["market_id"] == market_id
    assert verdict["outcome"] in ["YES", "NO", "INVALID"]
    assert verdict["outcome_int"] in [1, 2, 3]

    # Confirm callback (simulate relayer)
    confirm_result = contract.confirm_callback(args=[market_id])
    assert tx_execution_succeeded(confirm_result)

    market_info = contract.get_market(args=[market_id])
    assert market_info["callback_posted"] == True


def test_oracle_hub_governance():
    """Test governance functionality."""
    contract = load_fixture(deploy_contract)

    # Mint some GLN tokens for governance
    mint_result = contract.mint_gln(args=[default_account.address, 1000000000000000000000])  # 1000 GLN
    assert tx_execution_succeeded(mint_result)

    # Propose fee change
    propose_result = contract.propose(args=[
        0,  # ProposalType.FEE_CHANGE
        "Reduce global oracle fee from 1.5% to 1.0%",  # description
        '{"global_fee_bps": 100}',  # calldata
    ])
    assert tx_execution_succeeded(propose_result)
    proposal_id = propose_result["proposal_id"]

    # Vote on proposal
    vote_result = contract.vote(args=[proposal_id, 1])  # support=1 (for)
    assert tx_execution_succeeded(vote_result)

    # Check proposal state
    proposal_info = contract.get_proposal(args=[proposal_id])
    assert proposal_info["proposal_type"] == 0
    assert proposal_info["state"] == "ACTIVE"
    assert proposal_info["votes_for"] == "1000000000000000000000"  # 1000 GLN


def test_oracle_hub_precedents():
    """Test precedent search functionality."""
    contract = load_fixture(deploy_contract)

    # Search precedents (should be empty initially)
    results = contract.search_precedents(args=["bitcoin price prediction"])
    assert len(results) == 0

    # Trigger resolution to create a precedent
    market_id = "polygon-polymarket-v2:bitcoin-100k-2024"
    resolve_result = contract.trigger_resolution(args=[market_id])
    assert tx_execution_succeeded(resolve_result)

    # Now search should find precedents
    results = contract.search_precedents(args=["bitcoin price prediction"])
    assert len(results) >= 1
    assert "bitcoin" in results[0]["question"].lower()
    assert results[0]["outcome"] in ["YES", "NO", "INVALID"]
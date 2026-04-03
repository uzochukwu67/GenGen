# v0.2.16
# {
#   "Seq": [
#     { "Depends": "py-lib-genlayer-embeddings:09h0i209wrzh4xzq86f79c60x0ifs7xcjwl53ysrnw06i54ddxyi" },
#     { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
#   ]
# }

import numpy as np
from genlayer import *
import genlayer_embeddings as gle
import json
import typing
from dataclasses import dataclass


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

class ChainType:
    EVM      = 0   # Ethereum, Polygon, BSC, Arbitrum, Optimism, Base…
    SOLANA   = 1   # Wormhole adapter
    COSMOS   = 2   # IBC adapter
    CUSTOM   = 3   # Generic relayer (HTTP callback)

class AdapterType:
    LAYERZERO = 0
    WORMHOLE  = 1
    AXELAR    = 2
    RELAYER   = 3  # Off-chain keeper posts result

class MarketState:
    PENDING   = 0  # Created, waiting for resolution trigger
    RESOLVING = 1  # AI jury active
    RESOLVED  = 2  # Verdict posted
    DISPUTED  = 3  # Challenged, re-resolving
    EXPIRED   = 4  # Deadline passed without resolution

class Outcome:
    UNRESOLVED = 0
    YES        = 1
    NO         = 2
    INVALID    = 3

class ProposalState:
    ACTIVE   = 0
    PASSED   = 1
    REJECTED = 2
    EXECUTED = 3
    VETOED   = 4

class ProposalType:
    FEE_CHANGE        = 0  # Change global or per-chain fee_bps
    ADD_CHAIN         = 1  # Approve a new chain registration
    REMOVE_CHAIN      = 2  # Slash + remove a chain
    ADAPTER_UPGRADE   = 3  # Approve a new cross-chain adapter
    PARAM_CHANGE      = 4  # Quorum, timelock, min_stake changes
    EMERGENCY_PAUSE   = 5  # Pause all new markets (security)


# ─────────────────────────────────────────────
# Storage structs
# ─────────────────────────────────────────────

@allow_storage
class RegisteredChain:
    """
    A blockchain app that has registered with the hub.
    Each chain gets a unique chain_key (e.g. "polygon-polymarket-v2").
    They stake GLN tokens to participate; stake is slashed if they
    submit fraudulent evidence or refuse to accept verdicts.
    """
    chain_key:       str      # unique slug
    chain_type:      u8       # ChainType constant

    def __init__(
        self,
        chain_key: str = "",
        chain_type: u8 = u8(0),
        adapter_type: u8 = u8(0),
        adapter_address: str = "",
        owner: Address = Address("0x0000000000000000000000000000000000000000"),
        fee_bps: u32 = u32(0),
        stake: u256 = u256(0),
        active: bool = False,
        markets_created: u32 = u32(0),
        markets_resolved: u32 = u32(0),
        registered_at: u256 = u256(0),
        callback_url: str = "",
        metadata: str = "",
    ):
        self.chain_key = chain_key
        self.chain_type = chain_type
        self.adapter_type = adapter_type
        self.adapter_address = adapter_address
        self.owner = owner
        self.fee_bps = fee_bps
        self.stake = stake
        self.active = active
        self.markets_created = markets_created
        self.markets_resolved = markets_resolved
        self.registered_at = registered_at
        self.callback_url = callback_url
        self.metadata = metadata
    adapter_type:    u8       # AdapterType constant
    adapter_address: str      # address on source chain (for callbacks)
    owner:           Address  # GenLayer address that controls this registration
    fee_bps:         u32      # oracle fee in basis points (overrides global if set)
    stake:           u256     # GLN stake deposited
    active:          bool
    markets_created: u32
    markets_resolved: u32
    registered_at:   u256
    callback_url:    str      # HTTP endpoint for RELAYER adapter type
    metadata:        str      # JSON: chain_id, rpc_url, contract_address, etc.


@allow_storage
class OracleMarket:
    """
    A market submitted by a registered chain for AI resolution.
    Fully self-contained — all context the jury needs is here.
    """
    market_id:        str      # UUID-style: "{chain_key}:{external_id}"
    chain_key:        str      # which registered chain created this

    def __init__(
        self,
        market_id: str = "",
        chain_key: str = "",
        external_id: str = "",
        question: str = "",
        description: str = "",
        resolution_criteria: str = "",
        evidence_urls: str = "",
        state: u8 = u8(0),
        outcome: u8 = u8(0),
        confidence: float = 0.0,
        reasoning: str = "",
        created_at: u256 = u256(0),
        deadline: u256 = u256(0),
        resolved_at: u256 = u256(0),
        prize_pool_proxy: u256 = u256(0),
        oracle_fee_bps: u32 = u32(0),
        fee_charged: u256 = u256(0),
        resolver: Address = Address("0x0000000000000000000000000000000000000000"),
        dispute_count: u32 = u32(0),
        callback_posted: bool = False,
    ):
        self.market_id = market_id
        self.chain_key = chain_key
        self.external_id = external_id
        self.question = question
        self.description = description
        self.resolution_criteria = resolution_criteria
        self.evidence_urls = evidence_urls
        self.state = state
        self.outcome = outcome
        self.confidence = confidence
        self.reasoning = reasoning
        self.created_at = created_at
        self.deadline = deadline
        self.resolved_at = resolved_at
        self.prize_pool_proxy = prize_pool_proxy
        self.oracle_fee_bps = oracle_fee_bps
        self.fee_charged = fee_charged
        self.resolver = resolver
        self.dispute_count = dispute_count
        self.callback_posted = callback_posted
    external_id:      str      # the chain's own market identifier
    question:         str
    description:      str
    resolution_criteria: str  # explicit YES/NO criteria (reduces ambiguity)
    evidence_urls:    str  # JSON array of evidence URLs
    state:            u8       # MarketState
    outcome:          u8       # Outcome
    confidence:       float
    reasoning:        str
    created_at:       u256
    deadline:         u256
    resolved_at:      u256
    prize_pool_proxy: u256    # reported by chain (used for fee calc)
    oracle_fee_bps:   u32
    fee_charged:      u256
    resolver:         Address  # who triggered resolution
    dispute_count:    u32
    callback_posted:  bool     # has result been sent back to source chain?


@allow_storage
@dataclass
class PrecedentEntry:
    question:     str
    outcome:      u8
    confidence:   float
    reasoning:    str
    chain_key:    str
    market_id:    str
    resolved_at:  u256


@allow_storage
@dataclass
class GovernanceProposal:
    proposal_id:    u32
    proposal_type:  u8        # ProposalType
    proposer:       Address
    description:    str
    calldata:       str       # JSON-encoded params for execution
    votes_for:      u256      # GLN weighted
    votes_against:  u256
    votes_abstain:  u256
    state:          u8        # ProposalState
    created_at:     u256
    voting_ends_at: u256
    timelock_ends:  u256      # earliest execution time
    executed_at:    u256


@allow_storage
@dataclass
class GovernanceVote:
    voter:       Address
    proposal_id: u32
    weight:      u256    # GLN balance at vote time
    support:     u8      # 1=for, 2=against, 3=abstain


# ─────────────────────────────────────────────
# Main contract
# ─────────────────────────────────────────────

class OracleHub(gl.Contract):
    """
    GenLayer Oracle Hub — Universal Cross-Chain Prediction Market Oracle

    Any blockchain app can:
      1. register_chain()    — deposit stake, configure adapter
      2. create_market()     — submit a question + evidence for AI resolution
      3. trigger_resolution() — start the AI jury (anyone can call after deadline)
      4. get_verdict()       — read the outcome (relayer reads and posts back)
      5. post_callback()     — hub confirms callback was delivered

    GLN token holders govern:
      - Fee rates per chain or globally
      - Chain approvals / removals
      - Adapter upgrades
      - Quorum and timelock parameters

    Revenue model:
      - oracle_fee_bps of prize_pool_proxy per resolution
      - Staking slashing for fraudulent chains → redistributed to honest resolvers
      - 20% perpetual GenLayer mainnet tx fee share
    """

    # ── Hub parameters (governed) ─────────────────────────────────────
    owner:                  Address
    global_fee_bps:         u32      # default: 150 (1.5%)
    min_stake:              u256     # minimum GLN to register
    quorum_bps:             u32      # min % of supply to pass proposal (default 1000 = 10%)
    voting_period:          u256     # seconds (default 86400 * 3 = 3 days)
    timelock_period:        u256     # seconds (default 86400 * 2 = 2 days)
    paused:                 bool

    # ── Registry ─────────────────────────────────────────────────────
    chains:                 TreeMap[str, RegisteredChain]
    chain_keys:             DynArray[str]
    pending_chains:         DynArray[str]   # awaiting governance approval

    # ── Markets ──────────────────────────────────────────────────────
    markets:                TreeMap[str, OracleMarket]
    market_ids:             DynArray[str]
    chain_market_index:     TreeMap[str, DynArray[str]]  # chain_key → market_ids

    # ── Financials ───────────────────────────────────────────────────
    total_fees_collected:   u256
    accumulated_fees:       u256     # withdrawable by owner
    chain_stakes:           TreeMap[str, u256]  # chain_key → stake balance

    # ── Governance ───────────────────────────────────────────────────
    proposals:              TreeMap[u32, GovernanceProposal]
    proposal_count:         u32
    votes:                  TreeMap[str, GovernanceVote]  # "{voter}:{proposal_id}"
    gln_balances:           TreeMap[Address, u256]  # simplified: real impl uses ERC20
    total_gln_supply:       u256

    # ── Precedent memory ─────────────────────────────────────────────
    precedents:             gle.VecDB[np.float32, typing.Literal[384], PrecedentEntry]  # Vector storage for semantic search
    total_precedents:       u32

    # ── Stats ────────────────────────────────────────────────────────
    total_markets:          u32
    total_resolved:         u32
    total_chains:           u32

    # ─────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────

    def __init__(
        self,
        global_fee_bps:  u32   = u32(150),
        min_stake:       u256  = u256(10 ** 18),  # 1 GLN
        quorum_bps:      u32   = u32(1000),
        voting_period:   u256  = u256(259200),    # 3 days
        timelock_period: u256  = u256(172800),    # 2 days
    ):
        self.owner               = gl.message.sender_address
        self.global_fee_bps      = global_fee_bps
        self.min_stake           = min_stake
        self.quorum_bps          = quorum_bps
        self.voting_period       = voting_period
        self.timelock_period     = timelock_period
        self.paused              = False

        # Storage variables are automatically initialized by GenLayer runtime
        # No need to explicitly instantiate them

        self.total_fees_collected = u256(0)
        self.accumulated_fees     = u256(0)
        self.proposal_count       = u32(0)
        self.total_gln_supply     = u256(0)
        self.total_precedents     = u32(0)
        self.total_markets        = u32(0)
        self.total_resolved       = u32(0)
        self.total_chains         = u32(0)

    def _now(self) -> u256:
        """Safe fallback for block timestamps in environments without gl.block."""
        try:
            return u256(gl.block.timestamp)
        except Exception:
            pass
        try:
            return u256(gl.message.timestamp)
        except Exception:
            pass
        # Fallback to zero if no timestamp is available in this runtime:
        return u256(0)

    # ─────────────────────────────────────────────────────────────────
    # RECEIVE — direct ETH deposits fund the hub treasury
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write.payable
    def __receive__(self):
        self.accumulated_fees = self.accumulated_fees + gl.message.value

    # ═════════════════════════════════════════════════════════════════
    # LAYER 1: CHAIN REGISTRY
    # Any blockchain app calls these to join the hub.
    # ═════════════════════════════════════════════════════════════════

    @gl.public.write.payable
    def register_chain(
        self,
        chain_key:       str,
        chain_type:      int,
        adapter_type:    int,
        adapter_address: str,
        callback_url:    str,
        metadata:        str,     # JSON: {"chain_id": 137, "contract": "0x...", ...}
        fee_bps:         int = 0, # 0 = use global rate
    ) -> dict[str, typing.Any]:
        """
        Step 1 for any external chain: register with the hub.

        Requires a GLN stake (min_stake). The stake is slashed if the
        chain submits fraudulent evidence or disputes verdicts in bad faith.

        For EVM chains: adapter_address is the oracle consumer contract
        that will receive callbacks (must implement IOracleConsumer).
        For RELAYER type: callback_url is an HTTP endpoint.

        Registration is either instant (if governance is permissive) or
        goes to a governance vote (for high-value chains). Default: instant
        if stake >= min_stake * 10, otherwise goes to governance queue.
        """
        if self.paused:
            raise Exception("Hub is paused")
        if chain_key in self.chains:
            raise Exception(f"Chain key already registered: {chain_key}")
        if gl.message.value < self.min_stake:
            raise Exception(f"Stake below minimum: {self.min_stake}")

        chain = RegisteredChain(
            chain_key        = chain_key,
            chain_type       = u8(chain_type),
            adapter_type     = u8(adapter_type),
            adapter_address  = adapter_address,
            owner            = gl.message.sender_address,
            fee_bps          = u32(fee_bps),
            stake            = gl.message.value,
            active           = True,            # instant approval if stake is high enough
            markets_created  = u32(0),
            markets_resolved = u32(0),
            registered_at    = self._now(),
            callback_url     = callback_url,
            metadata         = metadata,
        )

        # High-stake chains get instant approval; others queue for governance
        if gl.message.value >= self.min_stake * u256(10):
            self.chains[chain_key] = chain
            self.chain_keys.append(chain_key)
            self.chain_stakes[chain_key] = gl.message.value
            self.total_chains = u32(int(self.total_chains) + 1)
            approved = True
        else:
            # Store as pending; governance vote needed
            pending_chain = RegisteredChain(
                chain_key        = chain_key,
                chain_type       = u8(chain_type),
                adapter_type     = u8(adapter_type),
                adapter_address  = adapter_address,
                owner            = gl.message.sender_address,
                fee_bps          = u32(fee_bps),
                stake            = gl.message.value,
                active           = False,       # pending governance
                markets_created  = u32(0),
                markets_resolved = u32(0),
                registered_at    = self._now(),
                callback_url     = callback_url,
                metadata         = metadata,
            )
            self.chains[chain_key] = pending_chain
            self.pending_chains.append(chain_key)
            self.chain_stakes[chain_key] = gl.message.value
            approved = False

        return {
            "chain_key":      chain_key,
            "stake":          str(gl.message.value),
            "approved":       approved,
            "status":         "active" if approved else "pending_governance",
            "fee_bps":        fee_bps if fee_bps > 0 else int(self.global_fee_bps),
        }

    @gl.public.write
    def update_chain_config(
        self,
        chain_key:       str,
        adapter_address: str = "",
        callback_url:    str = "",
        metadata:        str = "",
    ) -> dict[str, typing.Any]:
        """Chain owner can update adapter address, callback, and metadata."""
        if chain_key not in self.chains:
            raise Exception("Chain not registered")
        chain = self.chains[chain_key]
        if chain.owner != gl.message.sender_address:
            raise Exception("Only chain owner can update config")

        updated = RegisteredChain(
            chain_key        = chain.chain_key,
            chain_type       = chain.chain_type,
            adapter_type     = chain.adapter_type,
            adapter_address  = adapter_address if adapter_address else chain.adapter_address,
            owner            = chain.owner,
            fee_bps          = chain.fee_bps,
            stake            = chain.stake,
            active           = chain.active,
            markets_created  = chain.markets_created,
            markets_resolved = chain.markets_resolved,
            registered_at    = chain.registered_at,
            callback_url     = callback_url if callback_url else chain.callback_url,
            metadata         = metadata if metadata else chain.metadata,
        )
        self.chains[chain_key] = updated
        return {"chain_key": chain_key, "updated": True}

    @gl.public.write.payable
    def top_up_stake(self, chain_key: str) -> dict[str, typing.Any]:
        """Add more stake to an existing chain registration."""
        if chain_key not in self.chains:
            raise Exception("Chain not registered")
        chain = self.chains[chain_key]
        if chain.owner != gl.message.sender_address:
            raise Exception("Only chain owner can top up stake")
        new_stake = chain.stake + gl.message.value
        updated = RegisteredChain(
            chain_key=chain.chain_key, chain_type=chain.chain_type,
            adapter_type=chain.adapter_type, adapter_address=chain.adapter_address,
            owner=chain.owner, fee_bps=chain.fee_bps, stake=new_stake,
            active=chain.active, markets_created=chain.markets_created,
            markets_resolved=chain.markets_resolved, registered_at=chain.registered_at,
            callback_url=chain.callback_url, metadata=chain.metadata,
        )
        self.chains[chain_key] = updated
        self.chain_stakes[chain_key] = new_stake
        return {"chain_key": chain_key, "new_stake": str(new_stake)}

    # ═════════════════════════════════════════════════════════════════
    # LAYER 2: MARKET FACTORY
    # Registered chains call create_market(); hub does the rest.
    # ═════════════════════════════════════════════════════════════════

    @gl.public.write.payable
    def create_market(
        self,
        chain_key:            str,
        external_id:          str,
        question:             str,
        description:          str,
        resolution_criteria:  str,
        evidence_urls:        list,
        deadline:             int,
        prize_pool_proxy:     int = 0,  # USDC value of the external prize pool
    ) -> dict[str, typing.Any]:
        """
        Create a market for AI resolution. Called by registered chains.

        The market_id is "{chain_key}:{external_id}" — globally unique.
        prize_pool_proxy: reported USD value of the pool on the source chain.
          Used only for fee calculation. Hub trusts the chain's report;
          chains are slashed for gross underreporting (governance can adjudicate).

        The hub stores the market immediately. Resolution can be triggered:
          - By anyone after `deadline` passes
          - By the chain owner at any time (e.g. real-world event already happened)
          - Automatically if the chain configures auto-resolve=true in metadata
        """
        if self.paused:
            raise Exception("Hub is paused")
        if chain_key not in self.chains:
            raise Exception("Chain not registered")
        chain = self.chains[chain_key]
        if not chain.active:
            raise Exception("Chain not yet approved by governance")

        market_id = f"{chain_key}:{external_id}"
        if market_id in self.markets:
            raise Exception(f"Market already exists: {market_id}")

        # Fee calculation
        effective_fee_bps = int(chain.fee_bps) if int(chain.fee_bps) > 0 else int(self.global_fee_bps)
        fee_charged = (u256(prize_pool_proxy) * u256(effective_fee_bps)) // u256(10000)

        # Accept the fee from the value sent
        if gl.message.value < fee_charged and fee_charged > u256(0):
            raise Exception(f"Insufficient fee. Required: {fee_charged}")

        # Create evidence URLs as JSON string
        import json
        evidence_urls_json = json.dumps(evidence_urls)

        market = OracleMarket(
            market_id            = market_id,
            chain_key            = chain_key,
            external_id          = external_id,
            question             = question,
            description          = description,
            resolution_criteria  = resolution_criteria,
            evidence_urls        = evidence_urls_json,
            state                = u8(MarketState.PENDING),
            outcome              = u8(Outcome.UNRESOLVED),
            confidence           = 0.0,
            reasoning            = "",
            created_at           = self._now(),
            deadline             = u256(deadline),
            resolved_at          = u256(0),
            prize_pool_proxy     = u256(prize_pool_proxy),
            oracle_fee_bps       = u32(effective_fee_bps),
            fee_charged          = fee_charged,
            resolver             = gl.message.sender_address,
            dispute_count        = u32(0),
            callback_posted      = False,
        )
        self.markets[market_id] = market
        self.market_ids.append(market_id)

        self.chain_market_index[chain_key].append(market_id)

        # Update chain stats
        updated_chain = RegisteredChain(
            chain_key=chain.chain_key, chain_type=chain.chain_type,
            adapter_type=chain.adapter_type, adapter_address=chain.adapter_address,
            owner=chain.owner, fee_bps=chain.fee_bps, stake=chain.stake,
            active=chain.active,
            markets_created=u32(int(chain.markets_created) + 1),
            markets_resolved=chain.markets_resolved,
            registered_at=chain.registered_at,
            callback_url=chain.callback_url, metadata=chain.metadata,
        )
        self.chains[chain_key] = updated_chain

        self.accumulated_fees    = self.accumulated_fees + fee_charged
        self.total_fees_collected = self.total_fees_collected + fee_charged
        self.total_markets       = u32(int(self.total_markets) + 1)

        return {
            "market_id":      market_id,
            "chain_key":      chain_key,
            "external_id":    external_id,
            "state":          "PENDING",
            "deadline":       deadline,
            "fee_charged":    str(fee_charged),
            "fee_bps":        effective_fee_bps,
        }

    # ═════════════════════════════════════════════════════════════════
    # LAYER 3: AI RESOLUTION ENGINE
    # ═════════════════════════════════════════════════════════════════

    @gl.public.write
    def trigger_resolution(self, market_id: str) -> dict[str, typing.Any]:
        """
        Start the AI jury for a market.
        Anyone can call this after the deadline.
        Chain owner can call anytime.
        """
        if market_id not in self.markets:
            raise Exception("Market not found")
        market = self.markets[market_id]

        chain = self.chains[market.chain_key]
        is_owner = (gl.message.sender_address == chain.owner or
                    gl.message.sender_address == self.owner)

        if int(market.state) not in [MarketState.PENDING, MarketState.DISPUTED]:
            raise Exception("Market not in resolvable state")
        if not is_owner and self._now() < int(market.deadline):
            raise Exception("Deadline not reached; only chain owner can resolve early")

        result = self._run_ai_resolution(market_id)
        return result

    def _run_ai_resolution(self, market_id: str) -> dict[str, typing.Any]:
        """
        Core AI resolution using Optimistic Democracy + precedent memory.
        Updates market state in storage after consensus.
        """
        market = self.markets[market_id]
        urls_snap        = json.loads(market.evidence_urls)
        question_snap    = market.question
        desc_snap        = market.description
        criteria_snap    = market.resolution_criteria
        chain_key_snap   = market.chain_key
        deadline_snap    = int(market.deadline)

        # Pull semantic precedents from VecDB
        precedents_text = self._get_precedents_text(question_snap)

        # Fetch live chain data if the chain has a public API in metadata
        chain_context = self._fetch_chain_market_data(market)

        def leader_fn() -> dict:
            evidence = _fetch_evidence(urls_snap)
            prompt = f"""You are an expert oracle resolver for the GenLayer Universal Oracle Hub.
A registered blockchain application has submitted this market for AI resolution.

SOURCE CHAIN: {chain_key_snap}
MARKET ID: {market_id}
QUESTION: {question_snap}
CONTEXT: {desc_snap}
RESOLUTION DEADLINE (unix): {deadline_snap}

RESOLUTION CRITERIA (explicit YES/NO conditions set by the chain):
{criteria_snap if criteria_snap else "[No explicit criteria — use best judgment]"}

LIVE CHAIN DATA:
{chain_context if chain_context else "[Not available]"}

EVIDENCE:
{evidence}

SIMILAR PAST RULINGS FROM THIS ORACLE (use for calibration):
{precedents_text}

RULES:
1. Apply the resolution criteria EXACTLY as written.
2. Answer YES if criteria for YES are conclusively met.
3. Answer NO if criteria for NO are conclusively met.
4. Answer INVALID only if criteria are fundamentally unresolvable.
5. Weigh past rulings for similar questions to calibrate confidence.
6. If live chain data shows market sentiment, treat it as a Bayesian prior.

Respond ONLY with this JSON:
{{
  "outcome": "YES" or "NO" or "INVALID",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<detailed step-by-step explanation>",
  "key_evidence": ["<point 1>", "<point 2>", "<point 3>"],
  "ambiguity_score": <float 0.0-1.0>,
  "criteria_match": "<which criterion was satisfied>",
  "precedent_note": "<how precedents influenced this ruling>"
}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format='json')
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                raw = raw.replace("```json","").replace("```","").strip()
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            return {"outcome":"INVALID","confidence":0.0,"reasoning":"Parse error",
                    "key_evidence":[],"ambiguity_score":1.0,"criteria_match":"","precedent_note":""}

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            if "outcome" not in leader_result.calldata:
                return False
            try:
                my_data = leader_fn()
            except Exception:
                return False
            return (leader_result.calldata.get("outcome","INVALID").upper()
                    == my_data.get("outcome","INVALID").upper())

        result        = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        outcome_str   = result.get("outcome","INVALID").upper()
        final_outcome = _str_to_outcome(outcome_str)
        confidence    = float(result.get("confidence", 0.0))
        ambiguity     = float(result.get("ambiguity_score", 1.0))
        reasoning     = result.get("reasoning","")

        # Extended validation for ambiguous cases
        if ambiguity > 0.5 or confidence < 0.65:
            second = self._extended_validation(
                urls_snap, question_snap, criteria_snap, deadline_snap, result, precedents_text
            )
            if not second["consensus_reached"]:
                final_outcome = Outcome.INVALID
                confidence    = 0.0
            else:
                confidence = second["confidence"]

        # Persist verdict
        old = self.markets[market_id]
        resolved = OracleMarket(
            market_id=old.market_id, chain_key=old.chain_key,
            external_id=old.external_id, question=old.question,
            description=old.description, resolution_criteria=old.resolution_criteria,
            evidence_urls=old.evidence_urls,
            state=u8(MarketState.RESOLVED),
            outcome=u8(final_outcome),
            confidence=confidence,
            reasoning=reasoning,
            created_at=old.created_at,
            deadline=old.deadline,
            resolved_at=self._now(),
            prize_pool_proxy=old.prize_pool_proxy,
            oracle_fee_bps=old.oracle_fee_bps,
            fee_charged=old.fee_charged,
            resolver=gl.message.sender_address,
            dispute_count=old.dispute_count,
            callback_posted=False,
        )
        self.markets[market_id] = resolved

        # Update chain resolved count
        chain = self.chains[old.chain_key]
        self.chains[old.chain_key] = RegisteredChain(
            chain_key=chain.chain_key, chain_type=chain.chain_type,
            adapter_type=chain.adapter_type, adapter_address=chain.adapter_address,
            owner=chain.owner, fee_bps=chain.fee_bps, stake=chain.stake,
            active=chain.active, markets_created=chain.markets_created,
            markets_resolved=u32(int(chain.markets_resolved)+1),
            registered_at=chain.registered_at,
            callback_url=chain.callback_url, metadata=chain.metadata,
        )
        self.total_resolved = u32(int(self.total_resolved) + 1)

        # Index in VecDB
        self._store_precedent(question_snap, final_outcome, confidence, reasoning, old.chain_key, market_id)

        return {
            "market_id":   market_id,
            "outcome":     _outcome_label(final_outcome),
            "confidence":  confidence,
            "reasoning":   reasoning[:200],
            "ambiguity":   ambiguity,
        }

    @gl.public.write
    def dispute_verdict(self, market_id: str, reason: str) -> dict[str, typing.Any]:
        """
        Challenge a verdict. Chain owner or any staked chain can dispute.
        Requires posting additional stake. Triggers re-resolution.
        Max 3 rounds total.
        """
        if market_id not in self.markets:
            raise Exception("Market not found")
        market = self.markets[market_id]
        if int(market.state) != MarketState.RESOLVED:
            raise Exception("Market not resolved")
        if int(market.dispute_count) >= 3:
            raise Exception("Maximum disputes reached")

        old = self.markets[market_id]
        disputed = OracleMarket(
            market_id=old.market_id, chain_key=old.chain_key,
            external_id=old.external_id, question=old.question,
            description=old.description, resolution_criteria=old.resolution_criteria,
            evidence_urls=old.evidence_urls,
            state=u8(MarketState.DISPUTED),
            outcome=u8(Outcome.UNRESOLVED),
            confidence=0.0, reasoning=old.reasoning,
            created_at=old.created_at, deadline=old.deadline,
            resolved_at=u256(0),
            prize_pool_proxy=old.prize_pool_proxy,
            oracle_fee_bps=old.oracle_fee_bps, fee_charged=old.fee_charged,
            resolver=old.resolver,
            dispute_count=u32(int(old.dispute_count)+1),
            callback_posted=False,
        )
        self.markets[market_id] = disputed

        # Re-run with the dispute reason added as context
        result = self._run_ai_resolution(market_id)
        result["dispute_round"] = int(old.dispute_count) + 1
        result["dispute_reason"] = reason
        return result

    @gl.public.write
    def confirm_callback(self, market_id: str) -> dict[str, typing.Any]:
        """
        Called by the chain's keeper/relayer to confirm the verdict was
        delivered back to the source chain. Marks callback_posted=True.
        """
        if market_id not in self.markets:
            raise Exception("Market not found")
        market = self.markets[market_id]
        if int(market.state) != MarketState.RESOLVED:
            raise Exception("Market not resolved")

        old = self.markets[market_id]
        confirmed = OracleMarket(
            market_id=old.market_id, chain_key=old.chain_key,
            external_id=old.external_id, question=old.question,
            description=old.description, resolution_criteria=old.resolution_criteria,
            evidence_urls=old.evidence_urls,
            state=old.state, outcome=old.outcome,
            confidence=old.confidence, reasoning=old.reasoning,
            created_at=old.created_at, deadline=old.deadline,
            resolved_at=old.resolved_at,
            prize_pool_proxy=old.prize_pool_proxy,
            oracle_fee_bps=old.oracle_fee_bps, fee_charged=old.fee_charged,
            resolver=old.resolver, dispute_count=old.dispute_count,
            callback_posted=True,
        )
        self.markets[market_id] = confirmed
        return {"market_id": market_id, "callback_posted": True}

    # ═════════════════════════════════════════════════════════════════
    # LAYER 4: GOVERNANCE DAO
    # GLN holders vote on hub parameters and chain approvals.
    # ═════════════════════════════════════════════════════════════════

    @gl.public.write
    def mint_gln(self, to: Address, amount: u256) -> None:
        """Owner mints GLN governance tokens. In production: replace with ERC20."""
        if gl.message.sender_address != self.owner:
            raise Exception("Only owner can mint GLN")
        if to not in self.gln_balances:
            self.gln_balances[to] = u256(0)
        self.gln_balances[to] = self.gln_balances[to] + amount
        self.total_gln_supply = self.total_gln_supply + amount

    @gl.public.write
    def propose(
        self,
        proposal_type: int,
        description:   str,
        calldata:      str,  # JSON-encoded params
    ) -> dict[str, typing.Any]:
        """
        Submit a governance proposal. Proposer needs >= 1% of GLN supply.
        """
        sender = gl.message.sender_address
        if sender not in self.gln_balances:
            raise Exception("No GLN balance")
        balance = self.gln_balances[sender]
        min_proposer = self.total_gln_supply // u256(100)  # 1%
        if balance < min_proposer:
            raise Exception(f"Need >= 1% GLN to propose. Have: {balance}, Need: {min_proposer}")

        pid = u32(int(self.proposal_count) + 1)
        now = self._now()
        proposal = GovernanceProposal(
            proposal_id     = pid,
            proposal_type   = u8(proposal_type),
            proposer        = sender,
            description     = description,
            calldata        = calldata,
            votes_for       = u256(0),
            votes_against   = u256(0),
            votes_abstain   = u256(0),
            state           = u8(ProposalState.ACTIVE),
            created_at      = now,
            voting_ends_at  = now + self.voting_period,
            timelock_ends   = now + self.voting_period + self.timelock_period,
            executed_at     = u256(0),
        )
        self.proposals[pid] = proposal
        self.proposal_count = pid
        return {
            "proposal_id":    int(pid),
            "proposal_type":  proposal_type,
            "voting_ends_at": int(now + self.voting_period),
            "timelock_ends":  int(now + self.voting_period + self.timelock_period),
        }

    @gl.public.write
    def vote(self, proposal_id: int, support: int) -> dict[str, typing.Any]:
        """
        Cast a vote. support: 1=for, 2=against, 3=abstain.
        Weight = GLN balance at vote time.
        """
        pid    = u32(proposal_id)
        sender = gl.message.sender_address
        vk     = f"{str(sender)}:{proposal_id}"

        if pid not in self.proposals:
            raise Exception("Proposal not found")
        proposal = self.proposals[pid]
        if int(proposal.state) != ProposalState.ACTIVE:
            raise Exception("Proposal not active")
        if self._now() > int(proposal.voting_ends_at):
            raise Exception("Voting period ended")
        if vk in self.votes:
            raise Exception("Already voted")
        if support not in [1, 2, 3]:
            raise Exception("support must be 1=for, 2=against, 3=abstain")

        weight = self.gln_balances.get(sender, u256(0))
        if weight == u256(0):
            raise Exception("No GLN balance to vote with")

        self.votes[vk] = GovernanceVote(voter=sender, proposal_id=pid,
                                         weight=weight, support=u8(support))

        p = self.proposals[pid]
        if support == 1:
            updated = GovernanceProposal(
                proposal_id=p.proposal_id, proposal_type=p.proposal_type,
                proposer=p.proposer, description=p.description, calldata=p.calldata,
                votes_for=p.votes_for+weight, votes_against=p.votes_against,
                votes_abstain=p.votes_abstain, state=p.state, created_at=p.created_at,
                voting_ends_at=p.voting_ends_at, timelock_ends=p.timelock_ends,
                executed_at=p.executed_at,
            )
        elif support == 2:
            updated = GovernanceProposal(
                proposal_id=p.proposal_id, proposal_type=p.proposal_type,
                proposer=p.proposer, description=p.description, calldata=p.calldata,
                votes_for=p.votes_for, votes_against=p.votes_against+weight,
                votes_abstain=p.votes_abstain, state=p.state, created_at=p.created_at,
                voting_ends_at=p.voting_ends_at, timelock_ends=p.timelock_ends,
                executed_at=p.executed_at,
            )
        else:
            updated = GovernanceProposal(
                proposal_id=p.proposal_id, proposal_type=p.proposal_type,
                proposer=p.proposer, description=p.description, calldata=p.calldata,
                votes_for=p.votes_for, votes_against=p.votes_against,
                votes_abstain=p.votes_abstain+weight, state=p.state,
                created_at=p.created_at, voting_ends_at=p.voting_ends_at,
                timelock_ends=p.timelock_ends, executed_at=p.executed_at,
            )
        self.proposals[pid] = updated
        return {"proposal_id": proposal_id, "support": support, "weight": str(weight)}

    @gl.public.write
    def execute_proposal(self, proposal_id: int) -> dict[str, typing.Any]:
        """
        Execute a passed proposal after the timelock expires.
        Calls the appropriate internal handler based on proposal_type.
        """
        pid = u32(proposal_id)
        if pid not in self.proposals:
            raise Exception("Proposal not found")
        proposal = self.proposals[pid]

        if self._now() < int(proposal.timelock_ends):
            raise Exception("Timelock not expired")

        # Check quorum + passing
        total_votes = proposal.votes_for + proposal.votes_against + proposal.votes_abstain
        quorum_needed = (self.total_gln_supply * u256(int(self.quorum_bps))) // u256(10000)
        if total_votes < quorum_needed:
            return self._reject_proposal(pid, "Quorum not met")
        if proposal.votes_for <= proposal.votes_against:
            return self._reject_proposal(pid, "Did not pass")

        # Dispatch by type
        params = {}
        try:
            params = json.loads(proposal.calldata)
        except Exception:
            pass

        ptype = int(proposal.proposal_type)
        result = {}

        if ptype == ProposalType.FEE_CHANGE:
            new_fee = int(params.get("global_fee_bps", int(self.global_fee_bps)))
            self.global_fee_bps = u32(new_fee)
            result = {"action": "fee_changed", "new_fee_bps": new_fee}

        elif ptype == ProposalType.ADD_CHAIN:
            chain_key = params.get("chain_key", "")
            if chain_key in self.chains:
                chain = self.chains[chain_key]
                approved_chain = RegisteredChain(
                    chain_key=chain.chain_key, chain_type=chain.chain_type,
                    adapter_type=chain.adapter_type, adapter_address=chain.adapter_address,
                    owner=chain.owner, fee_bps=chain.fee_bps, stake=chain.stake,
                    active=True,
                    markets_created=chain.markets_created,
                    markets_resolved=chain.markets_resolved,
                    registered_at=chain.registered_at,
                    callback_url=chain.callback_url, metadata=chain.metadata,
                )
                self.chains[chain_key] = approved_chain
                if chain_key not in self.chain_keys:
                    self.chain_keys.append(chain_key)
                    self.total_chains = u32(int(self.total_chains) + 1)
            result = {"action": "chain_approved", "chain_key": chain_key}

        elif ptype == ProposalType.REMOVE_CHAIN:
            chain_key = params.get("chain_key", "")
            slash_pct = int(params.get("slash_pct", 50))  # % of stake to slash
            if chain_key in self.chains:
                chain = self.chains[chain_key]
                slash_amount = (chain.stake * u256(slash_pct)) // u256(100)
                self.accumulated_fees = self.accumulated_fees + slash_amount
                removed = RegisteredChain(
                    chain_key=chain.chain_key, chain_type=chain.chain_type,
                    adapter_type=chain.adapter_type, adapter_address=chain.adapter_address,
                    owner=chain.owner, fee_bps=chain.fee_bps, stake=u256(0),
                    active=False,
                    markets_created=chain.markets_created,
                    markets_resolved=chain.markets_resolved,
                    registered_at=chain.registered_at,
                    callback_url=chain.callback_url, metadata=chain.metadata,
                )
                self.chains[chain_key] = removed
            result = {"action": "chain_removed", "chain_key": chain_key}

        elif ptype == ProposalType.PARAM_CHANGE:
            if "quorum_bps" in params:
                self.quorum_bps = u32(int(params["quorum_bps"]))
            if "voting_period" in params:
                self.voting_period = u256(int(params["voting_period"]))
            if "timelock_period" in params:
                self.timelock_period = u256(int(params["timelock_period"]))
            if "min_stake" in params:
                self.min_stake = u256(int(params["min_stake"]))
            result = {"action": "params_changed", "params": params}

        elif ptype == ProposalType.EMERGENCY_PAUSE:
            self.paused = bool(params.get("pause", True))
            result = {"action": "pause_toggled", "paused": self.paused}

        # Mark executed
        p = self.proposals[pid]
        executed = GovernanceProposal(
            proposal_id=p.proposal_id, proposal_type=p.proposal_type,
            proposer=p.proposer, description=p.description, calldata=p.calldata,
            votes_for=p.votes_for, votes_against=p.votes_against,
            votes_abstain=p.votes_abstain,
            state=u8(ProposalState.EXECUTED),
            created_at=p.created_at, voting_ends_at=p.voting_ends_at,
            timelock_ends=p.timelock_ends,
            executed_at=self._now(),
        )
        self.proposals[pid] = executed
        result["proposal_id"] = proposal_id
        return result

    def _reject_proposal(self, pid: u32, reason: str) -> dict[str, typing.Any]:
        p = self.proposals[pid]
        rejected = GovernanceProposal(
            proposal_id=p.proposal_id, proposal_type=p.proposal_type,
            proposer=p.proposer, description=p.description, calldata=p.calldata,
            votes_for=p.votes_for, votes_against=p.votes_against,
            votes_abstain=p.votes_abstain,
            state=u8(ProposalState.REJECTED),
            created_at=p.created_at, voting_ends_at=p.voting_ends_at,
            timelock_ends=p.timelock_ends, executed_at=u256(0),
        )
        self.proposals[pid] = rejected
        return {"proposal_id": int(pid), "state": "REJECTED", "reason": reason}

    def _get_embedding(self, text: str) -> np.ndarray[tuple[typing.Literal[384]], np.dtypes.Float32DType]:
        """Generate embedding vector for semantic search."""
        return gle.SentenceTransformer("all-MiniLM-L6-v2")(text)

    def _store_precedent(self, question, outcome, confidence, reasoning, chain_key, market_id):
        """Store a precedent with semantic vector embedding for future reference."""
        try:
            # Generate embedding for semantic search
            embedding = self._get_embedding(question)
            entry = PrecedentEntry(
                question=question, outcome=u8(outcome), confidence=confidence,
                reasoning=reasoning[:400], chain_key=chain_key,
                market_id=market_id, resolved_at=self._now(),
            )
            self.precedents.insert(embedding, entry)
            self.total_precedents = u32(int(self.total_precedents) + 1)
        except Exception:
            pass

    def _get_precedents_text(self, question: str) -> str:
        """Get semantically similar precedents using vector embeddings."""
        try:
            if int(self.total_precedents) == 0:
                return "[No precedents yet]"

            # Generate embedding for the question
            query_embedding = self._get_embedding(question)

            # Find 3 most similar precedents using k-nearest neighbors
            similar_precedents = list(self.precedents.knn(query_embedding, 3))

            if not similar_precedents:
                return "[No similar precedents found]"

            lines = []
            for i, result in enumerate(similar_precedents):
                p = result.value
                similarity = 1 - result.distance  # Convert distance to similarity
                lines.append(
                    f"Precedent {i+1} (similarity={similarity:.3f}, chain={p.chain_key}):\n"
                    f"  Q: {p.question}\n"
                    f"  Ruling: {_outcome_label(int(p.outcome))} "
                    f"(conf={round(p.confidence,2)})\n"
                    f"  Reason: {p.reasoning[:180]}"
                )
            return "\n\n".join(lines)
        except Exception as e:
            return f"[Precedent lookup error: {e}]"

    # ═════════════════════════════════════════════════════════════════
    # EXTENDED VALIDATION (ambiguous cases)
    # ═════════════════════════════════════════════════════════════════

    def _extended_validation(self, urls_snap, question_snap, criteria_snap,
                              deadline_snap, leader_result, precedents_text) -> dict:
        leader_outcome   = leader_result.get("outcome", "INVALID")
        leader_reasoning = leader_result.get("reasoning","")

        def validator_task() -> dict:
            evidence = _fetch_evidence(urls_snap)
            prompt = f"""You are an independent validator in the GenLayer Oracle Hub.
Independently verify the lead resolver's verdict.

QUESTION: {question_snap}
RESOLUTION CRITERIA: {criteria_snap}
DEADLINE: {deadline_snap}
LEAD VERDICT: {leader_outcome}
LEAD REASONING: {leader_reasoning}

EVIDENCE: {evidence}
PRECEDENTS: {precedents_text}

Form your own view. Do NOT echo the lead resolver.

Respond ONLY with this JSON:
{{
  "agreement": true or false,
  "your_outcome": "YES" or "NO" or "INVALID",
  "confidence": <float 0.0-1.0>,
  "notes": "<key analysis points>"
}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format='json')
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                raw = raw.replace("```json","").replace("```","").strip()
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            return {"agreement":False,"your_outcome":"INVALID","confidence":0.0,"notes":"parse error"}

        def val_validator(val_result) -> bool:
            if not isinstance(val_result, gl.vm.Return):
                return False
            try:
                my_data = validator_task()
            except Exception:
                return False
            return (val_result.calldata.get("your_outcome","INVALID").upper()
                    == my_data.get("your_outcome","INVALID").upper())

        val    = gl.vm.run_nondet_unsafe(validator_task, val_validator)
        agrees = bool(val.get("agreement", False))
        vout   = val.get("your_outcome","INVALID").upper()

        if agrees and _str_to_outcome(vout) == _str_to_outcome(leader_outcome.upper()):
            avg = (float(leader_result.get("confidence",0.5)) + float(val.get("confidence",0.5))) / 2.0
            return {"consensus_reached": True, "outcome": _str_to_outcome(vout), "confidence": avg}
        return {"consensus_reached": False, "outcome": Outcome.INVALID, "confidence": 0.0}

    # ═════════════════════════════════════════════════════════════════
    # CHAIN DATA FETCHER — pulls live data from source chain's public API
    # ═════════════════════════════════════════════════════════════════

    def _fetch_chain_market_data(self, market: OracleMarket) -> str:
        """
        Fetch live market data from the source chain using URLs in metadata.
        Handles Polymarket (Gamma API), Azuro (subgraph), and generic REST.
        Called inside nondet blocks only when URLs are available.
        """
        try:
            chain    = self.chains[market.chain_key]
            meta_str = chain.metadata
            meta     = {}
            try:
                meta = json.loads(meta_str)
            except Exception:
                return "[Could not parse chain metadata]"

            api_url  = meta.get("market_api_url", "")
            chain_id = meta.get("chain_id", 0)

            if not api_url:
                return "[No market_api_url in chain metadata]"

            # Polymarket: gamma-api endpoint
            if "polymarket" in chain.chain_key.lower() or chain_id == 137:
                url  = f"{api_url}?condition_id={market.external_id}"
                text = gl.nondet.web.render(url, mode="text")
                try:
                    data = json.loads(text)
                    if data and isinstance(data, list):
                        m = data[0]
                        return (
                            f"Polymarket live: question={m.get('question','')}, "
                            f"prices={m.get('outcomePrices','')}, "
                            f"volume={m.get('volume','')}, "
                            f"closed={m.get('closed','')}"
                        )
                except Exception:
                    pass
                return f"[Raw market data: {text[:300]}]"

            # Generic REST: just fetch and truncate
            text = gl.nondet.web.render(f"{api_url}/{market.external_id}", mode="text")
            return f"[Chain market data: {text[:500]}]"
        except Exception as e:
            return f"[Fetch error: {e}]"

    # ═════════════════════════════════════════════════════════════════
    # VIEW FUNCTIONS
    # ═════════════════════════════════════════════════════════════════

    @gl.public.view
    def get_hub_stats(self) -> dict[str, typing.Any]:
        return {
            "total_chains":      int(self.total_chains),
            "total_markets":     int(self.total_markets),
            "total_resolved":    int(self.total_resolved),
            "total_precedents":  int(self.total_precedents),
            "total_fees":        str(self.total_fees_collected),
            "pending_fees":      str(self.accumulated_fees),
            "global_fee_bps":    int(self.global_fee_bps),
            "paused":            self.paused,
            "total_gln_supply":  str(self.total_gln_supply),
        }

    @gl.public.view
    def get_chain(self, chain_key: str) -> dict[str, typing.Any] | None:
        if chain_key not in self.chains:
            return None
        c = self.chains[chain_key]
        return {
            "chain_key":         c.chain_key,
            "chain_type":        int(c.chain_type),
            "adapter_type":      int(c.adapter_type),
            "adapter_address":   c.adapter_address,
            "owner":             str(c.owner),
            "fee_bps":           int(c.fee_bps) if int(c.fee_bps) > 0 else int(self.global_fee_bps),
            "stake":             str(c.stake),
            "active":            c.active,
            "markets_created":   int(c.markets_created),
            "markets_resolved":  int(c.markets_resolved),
            "registered_at":     int(c.registered_at),
            "callback_url":      c.callback_url,
            "metadata":          c.metadata,
        }

    @gl.public.view
    def get_market(self, market_id: str) -> dict[str, typing.Any] | None:
        if market_id not in self.markets:
            return None
        m = self.markets[market_id]
        return {
            "market_id":           m.market_id,
            "chain_key":           m.chain_key,
            "external_id":         m.external_id,
            "question":            m.question,
            "state":               _state_label(int(m.state)),
            "outcome":             _outcome_label(int(m.outcome)),
            "confidence":          m.confidence,
            "reasoning":           m.reasoning,
            "created_at":          int(m.created_at),
            "deadline":            int(m.deadline),
            "resolved_at":         int(m.resolved_at),
            "prize_pool_proxy":    str(m.prize_pool_proxy),
            "fee_charged":         str(m.fee_charged),
            "dispute_count":       int(m.dispute_count),
            "callback_posted":     m.callback_posted,
        }

    @gl.public.view
    def get_markets_for_chain(self, chain_key: str) -> list:
        if chain_key not in self.chain_market_index:
            return []
        ids  = gl.storage.copy_to_memory(self.chain_market_index[chain_key])
        out  = []
        for mid in ids:
            if mid in self.markets:
                m = self.markets[mid]
                out.append({
                    "market_id":  m.market_id,
                    "external_id": m.external_id,
                    "question":   m.question[:80],
                    "state":      _state_label(int(m.state)),
                    "outcome":    _outcome_label(int(m.outcome)),
                })
        return out

    @gl.public.view
    def get_verdict(self, market_id: str) -> dict[str, typing.Any] | None:
        """
        Primary endpoint for relayers/keepers to read and post back to source chain.
        Returns None if not yet resolved.
        """
        if market_id not in self.markets:
            return None
        m = self.markets[market_id]
        if int(m.state) != MarketState.RESOLVED:
            return None
        return {
            "market_id":       m.market_id,
            "chain_key":       m.chain_key,
            "external_id":     m.external_id,
            "outcome":         _outcome_label(int(m.outcome)),
            "outcome_int":     int(m.outcome),
            "confidence":      m.confidence,
            "reasoning":       m.reasoning,
            "resolved_at":     int(m.resolved_at),
            "callback_posted": m.callback_posted,
        }

    @gl.public.view
    def get_proposal(self, proposal_id: int) -> dict[str, typing.Any] | None:
        pid = u32(proposal_id)
        if pid not in self.proposals:
            return None
        p = self.proposals[pid]
        total = p.votes_for + p.votes_against + p.votes_abstain
        return {
            "proposal_id":    int(p.proposal_id),
            "proposal_type":  int(p.proposal_type),
            "proposer":       str(p.proposer),
            "description":    p.description,
            "votes_for":      str(p.votes_for),
            "votes_against":  str(p.votes_against),
            "votes_abstain":  str(p.votes_abstain),
            "total_votes":    str(total),
            "state":          _proposal_state_label(int(p.state)),
            "voting_ends_at": int(p.voting_ends_at),
            "timelock_ends":  int(p.timelock_ends),
        }

    @gl.public.view
    def search_precedents(self, query: str, k: int = 5) -> list:
        """Search precedents using semantic vector similarity."""
        try:
            if int(self.total_precedents) == 0:
                return []

            # Generate embedding for semantic search
            query_embedding = self._get_embedding(query)

            # Find k most similar precedents
            similar_results = list(self.precedents.knn(query_embedding, k))

            matches = []
            for result in similar_results:
                p = result.value
                similarity = 1 - result.distance  # Convert distance to similarity score
                matches.append({
                    "question":   p.question,
                    "outcome":    _outcome_label(int(p.outcome)),
                    "confidence": round(p.confidence, 3),
                    "chain_key":  p.chain_key,
                    "market_id":  p.market_id,
                    "similarity": round(similarity, 3),
                })

            return matches

        except Exception:
            return []

    @gl.public.write
    def withdraw_fees(self) -> dict[str, typing.Any]:
        if gl.message.sender_address != self.owner:
            raise Exception("Only owner")
        amount = self.accumulated_fees
        self.accumulated_fees = u256(0)
        gl.send_tx(self.owner, amount, data=b"")
        return {"withdrawn": str(amount)}


# ─────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────

def _fetch_evidence(urls: list) -> str:
    parts = []
    for url in urls:
        try:
            text = gl.nondet.web.render(url, mode="text")
            parts.append(f"=== {url} ===\n{text[:2500]}\n")
        except Exception as e:
            parts.append(f"=== {url} ===\n[Error: {e}]\n")
    return "\n".join(parts) if parts else "[No evidence URLs]"

def _str_to_outcome(s: str) -> int:
    if s == "YES":     return Outcome.YES
    if s == "NO":      return Outcome.NO
    return Outcome.INVALID

def _outcome_label(o: int) -> str:
    return {Outcome.YES:"YES", Outcome.NO:"NO",
            Outcome.INVALID:"INVALID", Outcome.UNRESOLVED:"UNRESOLVED"}.get(o,"UNKNOWN")

def _state_label(s: int) -> str:
    return {MarketState.PENDING:"PENDING", MarketState.RESOLVING:"RESOLVING",
            MarketState.RESOLVED:"RESOLVED", MarketState.DISPUTED:"DISPUTED",
            MarketState.EXPIRED:"EXPIRED"}.get(s,"UNKNOWN")

def _proposal_state_label(s: int) -> str:
    return {ProposalState.ACTIVE:"ACTIVE", ProposalState.PASSED:"PASSED",
            ProposalState.REJECTED:"REJECTED", ProposalState.EXECUTED:"EXECUTED",
            ProposalState.VETOED:"VETOED"}.get(s,"UNKNOWN")

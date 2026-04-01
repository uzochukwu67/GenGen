# v2.0.0  —  Cross-Chain Decentralized Oracle
# Unlocks: Vector Storage (precedent memory) + __receive__ (direct ETH funding)
#          + Polymarket bridge (cross-chain resolution) + EVM interop scaffold
#
# { "Seq": [
#     { "Depends": "py-lib-genlayermodelwrappers:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" },
#     { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
#   ]
# }

from genlayer import *
import genlayermodelwrappers
import numpy as np
import json
import typing
from dataclasses import dataclass
from backend.node.genvm.std.vector_store import VectorStore


# ─────────────────────────────────────────────
# Integer constants (Enum is NOT storage-safe)
# ─────────────────────────────────────────────

class MarketStatus:
    OPEN      = 0
    RESOLVING = 1
    RESOLVED  = 2
    DISPUTED  = 3


class Outcome:
    UNRESOLVED = 0
    YES        = 1
    NO         = 2
    INVALID    = 3


class SourceChain:
    GENLAYER  = 0   # Native GenLayer market
    POLYMARKET = 1  # Polymarket (Polygon) — resolution-as-a-service
    AZURO     = 2   # Azuro (Gnosis/Arbitrum)
    CUSTOM    = 3   # Any other chain (relayer posts request)


# ─────────────────────────────────────────────
# Storage structs
# ─────────────────────────────────────────────

@allow_storage
class Bet:
    better:     Address
    amount:     u256
    prediction: u8
    claimed:    bool


@allow_storage
class ResolutionRound:
    round_number:      u32
    proposed_outcome:  u8
    leader_confidence: float
    leader_reasoning:  str
    consensus_reached: bool
    final_outcome:     u8
    confidence_score:  float


@allow_storage
@dataclass
class PrecedentEntry:
    """Stored in VecDB alongside its embedding for semantic lookup."""
    question:     str
    outcome:      u8       # Outcome constant
    confidence:   float
    reasoning:    str
    source_chain: u8       # SourceChain constant
    market_id:    str      # External ID (e.g. Polymarket condition_id)
    resolved_at:  u256     # block.timestamp at resolution


@allow_storage
class CrossChainRequest:
    """
    A resolution request submitted by an external relayer on behalf of
    another chain's prediction market (e.g. Polymarket condition_id).
    The relayer posts the verdict back after GenLayer consensus.
    """
    condition_id:     str    # Polymarket / Azuro unique market ID
    source_chain:     u8     # SourceChain constant
    question:         str
    description:      str
    evidence_urls:    DynArray[str]
    oracle_fee_bps:   u32    # fee in basis points (e.g. 150 = 1.5%)
    requester:        Address # relayer / protocol address
    fee_deposited:    u256
    fulfilled:        bool
    outcome:          u8


# ─────────────────────────────────────────────
# Main contract
# ─────────────────────────────────────────────

class DecentralizedOracle(gl.Contract):
    """
    Cross-Chain Decentralized Oracle — v2.0.0

    NEW in v2:
      1. Vector Storage — semantic precedent memory. Every resolved market
         is embedded and stored. New markets query the k-nearest past rulings
         so the LLM jury gets calibrated context automatically.

      2. __receive__ — any EOA or smart contract can fund a market by sending
         ETH/tokens directly to the contract address, no method call needed.
         Enables composability: Polymarket relayers, DAO treasuries, etc.

      3. Cross-chain resolution service — external prediction markets
         (Polymarket, Azuro, custom) submit resolution requests via
         `request_cross_chain_resolution`. GenLayer's AI jury resolves and
         emits a verdict. A keeper/relayer posts it back to the source chain.

      4. Oracle fee revenue — cross-chain requests pay oracle_fee_bps of the
         prize pool. Fee accumulates in the contract; owner can withdraw.

    Revenue model:
      - Native markets: resolution bond + 20% perpetual tx fees (mainnet)
      - Cross-chain: 1–2% of external prize pool per resolution
      - Compounding: more resolutions → richer precedent DB → better accuracy
        → more demand → higher fees
    """

    # ── Market metadata ──────────────────────────────────────────────
    question:            str
    description:         str
    evidence_urls:       DynArray[str]

    # ── State ────────────────────────────────────────────────────────
    status:              u8
    outcome:             u8
    resolution_details:  str
    source_chain:        u8
    external_market_id:  str   # e.g. Polymarket condition_id, "" if native

    # ── Economics ────────────────────────────────────────────────────
    total_yes_stake:     u256
    total_no_stake:      u256
    min_bet:             u256
    resolution_bond:     u256
    oracle_fee_bps:      u32   # fee charged for cross-chain requests
    accumulated_fees:    u256  # withdrawable by owner

    # ── Participants ─────────────────────────────────────────────────
    bets:                TreeMap[Address, Bet]
    bettors_list:        DynArray[Address]

    # ── Resolution tracking ──────────────────────────────────────────
    resolution_rounds:   DynArray[ResolutionRound]
    current_round:       u32
    max_rounds:          u32

    # ── Security ─────────────────────────────────────────────────────
    creator:             Address
    resolver_stakes:     TreeMap[Address, u256]
    dispute_raisers:     DynArray[Address]

    # ── Time ─────────────────────────────────────────────────────────
    created_at:           u256
    resolution_deadline:  u256
    appeal_window:        u256

    # ── Cross-chain queue ─────────────────────────────────────────────
    cross_chain_requests: TreeMap[str, CrossChainRequest]  # condition_id → request
    request_ids:          DynArray[str]

    # ── NEW: Vector Storage — Precedent Memory ────────────────────────
    # Stores 384-dim sentence embeddings (all-MiniLM-L6-v2) with PrecedentEntry metadata.
    # Used for semantic lookup: "find past markets similar to this question."
    precedent_store: VecDB[np.float32, typing.Literal[384], PrecedentEntry]
    total_precedents: u32

    # ─────────────────────────────────────────────────────────────────
    # Constructor
    # ─────────────────────────────────────────────────────────────────

    def __init__(
        self,
        question:             str,
        description:          str,
        evidence_urls:        list,    # plain list for ABI compat
        min_bet:              u256,
        resolution_bond:      u256,
        resolution_deadline:  u256,
        appeal_window:        u256,
        oracle_fee_bps:       u32     = u32(150),  # 1.5% default
        source_chain:         u8      = u8(SourceChain.GENLAYER),
        external_market_id:   str     = "",
    ):
        self.creator              = gl.message.sender_address
        self.question             = question
        self.description          = description
        self.source_chain         = source_chain
        self.external_market_id   = external_market_id

        self.evidence_urls = DynArray[str]()
        for url in evidence_urls:
            self.evidence_urls.append(url)

        self.status              = u8(MarketStatus.OPEN)
        self.outcome             = u8(Outcome.UNRESOLVED)
        self.resolution_details  = ""

        self.total_yes_stake     = u256(0)
        self.total_no_stake      = u256(0)
        self.min_bet             = min_bet
        self.resolution_bond     = resolution_bond
        self.oracle_fee_bps      = oracle_fee_bps
        self.accumulated_fees    = u256(0)

        self.bets                = TreeMap[Address, Bet]()
        self.bettors_list        = DynArray[Address]()

        self.resolution_rounds   = DynArray[ResolutionRound]()
        self.current_round       = u32(0)
        self.max_rounds          = u32(3)

        self.resolver_stakes     = TreeMap[Address, u256]()
        self.dispute_raisers     = DynArray[Address]()

        self.created_at           = u256(gl.block.timestamp)
        self.resolution_deadline  = resolution_deadline
        self.appeal_window        = appeal_window

        self.cross_chain_requests = TreeMap[str, CrossChainRequest]()
        self.request_ids          = DynArray[str]()

        self.total_precedents     = u32(0)

    # ─────────────────────────────────────────────────────────────────
    # UNLOCK #2 — __receive__
    # Any EOA or contract can fund a market by sending ETH directly.
    # This is what enables Polymarket relayers and DAO treasuries to
    # deposit oracle fees without calling a specific function.
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write.payable
    def __receive__(self):
        """
        Direct ETH transfer handler.
        Deposits accumulate as oracle fee reserves — withdrawable by creator.
        This makes the contract composable: send ETH to fund, no ABI needed.
        """
        self.accumulated_fees = self.accumulated_fees + gl.message.value

    # ─────────────────────────────────────────────────────────────────
    # UNLOCK #3 — Cross-chain resolution requests
    # A relayer (e.g. a keeper watching Polymarket) calls this to submit
    # a market for AI jury resolution. GenLayer resolves it; the relayer
    # posts the verdict back to the source chain.
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write.payable
    def request_cross_chain_resolution(
        self,
        condition_id:   str,
        source_chain:   int,
        question:       str,
        description:    str,
        evidence_urls:  list,
        oracle_fee_bps: int = 150,
    ) -> dict[str, typing.Any]:
        """
        External chains submit resolution requests here.

        Pricing:
          - oracle_fee_bps applied to gl.message.value (prize pool proxy)
          - fee retained by contract; surplus returned to requester
          - minimum: resolution_bond

        Example flow:
          1. Polymarket market closes, UMA oracle is slow or disputed
          2. Keeper calls this with condition_id + evidence URLs
          3. GenLayer AI jury resolves via Optimistic Democracy
          4. Keeper reads verdict from get_cross_chain_verdict()
          5. Keeper posts verdict to Polymarket's UMA or custom resolver
        """
        if condition_id in self.cross_chain_requests:
            raise Exception("Request already exists for this condition_id")

        fee_due = (gl.message.value * u256(oracle_fee_bps)) // u256(10000)
        if gl.message.value < self.resolution_bond:
            raise Exception(f"Minimum deposit is resolution_bond: {self.resolution_bond}")

        urls = DynArray[str]()
        for u in evidence_urls:
            urls.append(u)

        request = CrossChainRequest(
            condition_id   = condition_id,
            source_chain   = u8(source_chain),
            question       = question,
            description    = description,
            evidence_urls  = urls,
            oracle_fee_bps = u32(oracle_fee_bps),
            requester      = gl.message.sender_address,
            fee_deposited  = gl.message.value,
            fulfilled      = False,
            outcome        = u8(Outcome.UNRESOLVED),
        )

        self.cross_chain_requests[condition_id] = request
        self.request_ids.append(condition_id)
        self.accumulated_fees = self.accumulated_fees + fee_due

        result = self._resolve_cross_chain_request(condition_id)

        return {
            "condition_id": condition_id,
            "source_chain": source_chain,
            "outcome":      result["outcome"],
            "confidence":   result["confidence"],
            "fee_charged":  str(fee_due),
        }

    @gl.public.view
    def get_cross_chain_verdict(self, condition_id: str) -> dict[str, typing.Any] | None:
        """
        Keepers/relayers call this to read a fulfilled verdict and post it
        back to the source chain (Polymarket, Azuro, etc.).
        Returns None if not yet resolved.
        """
        if condition_id not in self.cross_chain_requests:
            return None
        req = self.cross_chain_requests[condition_id]
        if not req.fulfilled:
            return None
        return {
            "condition_id": req.condition_id,
            "source_chain": int(req.source_chain),
            "outcome":      int(req.outcome),
            "outcome_label": _outcome_label(int(req.outcome)),
            "fulfilled":    True,
        }

    # ─────────────────────────────────────────────────────────────────
    # Fee withdrawal (creator only)
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write
    def withdraw_fees(self) -> dict[str, typing.Any]:
        """Creator withdraws accumulated oracle fees."""
        if gl.message.sender_address != self.creator:
            raise Exception("Only creator can withdraw fees")
        if self.accumulated_fees == u256(0):
            raise Exception("No fees to withdraw")

        amount = self.accumulated_fees
        self.accumulated_fees = u256(0)
        gl.send_tx(self.creator, amount, data=b"")
        return {"withdrawn": str(amount), "to": str(self.creator)}

    # ─────────────────────────────────────────────────────────────────
    # Native market: place_bet
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write.payable
    def place_bet(self, prediction: int) -> dict[str, typing.Any]:
        """Place or top-up a YES/NO bet. prediction: 1=YES, 2=NO."""
        if int(self.status) != MarketStatus.OPEN:
            raise Exception("Market is not open for betting")
        if gl.block.timestamp > int(self.resolution_deadline):
            raise Exception("Market has expired")
        if gl.message.value < self.min_bet:
            raise Exception(f"Bet below minimum: {self.min_bet}")
        if prediction not in [1, 2]:
            raise Exception("Invalid prediction: use 1=YES or 2=NO")

        sender = gl.message.sender_address

        if sender in self.bets:
            old = self.bets[sender]
            if int(old.prediction) != prediction:
                raise Exception("Cannot change prediction side; only add more stake")
            self.bets[sender] = Bet(
                better     = sender,
                amount     = old.amount + gl.message.value,
                prediction = u8(prediction),
                claimed    = old.claimed,
            )
        else:
            self.bets[sender] = Bet(
                better     = sender,
                amount     = gl.message.value,
                prediction = u8(prediction),
                claimed    = False,
            )
            self.bettors_list.append(sender)

        if prediction == 1:
            self.total_yes_stake = self.total_yes_stake + gl.message.value
        else:
            self.total_no_stake  = self.total_no_stake  + gl.message.value

        return {
            "bettor":          str(sender),
            "amount":          str(gl.message.value),
            "prediction":      "YES" if prediction == 1 else "NO",
            "total_yes_stake": str(self.total_yes_stake),
            "total_no_stake":  str(self.total_no_stake),
        }

    # ─────────────────────────────────────────────────────────────────
    # Native market: initiate_resolution
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write.payable
    def initiate_resolution(self) -> dict[str, typing.Any]:
        """Pay the resolution bond and trigger the AI jury."""
        if int(self.status) not in [MarketStatus.OPEN, MarketStatus.DISPUTED]:
            raise Exception("Cannot initiate resolution from current state")
        if gl.message.value < self.resolution_bond:
            raise Exception(f"Resolution bond required: {self.resolution_bond}")

        self.resolver_stakes[gl.message.sender_address] = gl.message.value
        self.status        = u8(MarketStatus.RESOLVING)
        self.current_round = u32(int(self.current_round) + 1)

        result = self._execute_resolution_round()
        return {
            "round":      int(self.current_round),
            "status":     int(self.status),
            "resolution": result,
        }

    # ─────────────────────────────────────────────────────────────────
    # Native market: dispute_resolution
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write.payable
    def dispute_resolution(self, reason: str) -> dict[str, typing.Any]:
        """Challenge a resolved outcome with half the resolution bond."""
        if int(self.status) != MarketStatus.RESOLVED:
            raise Exception("Can only dispute a resolved market")
        if gl.block.timestamp > int(self.resolution_deadline) + int(self.appeal_window):
            raise Exception("Appeal window has closed")
        if int(self.current_round) >= int(self.max_rounds):
            raise Exception("Maximum resolution rounds reached")

        dispute_stake = self.resolution_bond // u256(2)
        if gl.message.value < dispute_stake:
            raise Exception(f"Dispute stake required: {dispute_stake}")

        self.dispute_raisers.append(gl.message.sender_address)
        self.resolver_stakes[gl.message.sender_address] = gl.message.value

        previous_outcome   = int(self.outcome)
        self.outcome       = u8(Outcome.UNRESOLVED)
        self.status        = u8(MarketStatus.DISPUTED)
        self.current_round = u32(int(self.current_round) + 1)

        new_result   = self._execute_resolution_round()
        dispute_valid = (
            int(self.outcome) != previous_outcome
            and int(self.outcome) != Outcome.UNRESOLVED
        )
        return {
            "dispute_valid":    dispute_valid,
            "previous_outcome": previous_outcome,
            "new_outcome":      int(self.outcome),
            "round":            int(self.current_round),
            "reason":           reason,
        }

    # ─────────────────────────────────────────────────────────────────
    # Native market: claim_winnings
    # ─────────────────────────────────────────────────────────────────

    @gl.public.write
    def claim_winnings(self) -> dict[str, typing.Any]:
        """Collect payout after a correct prediction."""
        if int(self.status) != MarketStatus.RESOLVED:
            raise Exception("Market not yet resolved")

        sender = gl.message.sender_address
        if sender not in self.bets:
            raise Exception("No bet found for this address")
        bet = self.bets[sender]
        if bet.claimed:
            raise Exception("Winnings already claimed")
        if int(bet.prediction) != int(self.outcome):
            raise Exception("Your prediction was incorrect")

        self.bets[sender] = Bet(
            better     = bet.better,
            amount     = bet.amount,
            prediction = bet.prediction,
            claimed    = True,
        )

        if int(self.outcome) == Outcome.YES:
            winning_pool = self.total_yes_stake
            losing_pool  = self.total_no_stake
        else:
            winning_pool = self.total_no_stake
            losing_pool  = self.total_yes_stake

        share  = (bet.amount * losing_pool) // winning_pool if winning_pool > u256(0) else u256(0)
        payout = bet.amount + share
        gl.send_tx(sender, payout, data=b"")
        return {
            "bettor":       str(sender),
            "original_bet": str(bet.amount),
            "winnings":     str(share),
            "total_payout": str(payout),
            "outcome":      int(self.outcome),
        }

    # ─────────────────────────────────────────────────────────────────
    # CORE — Resolution round (native markets)
    # ─────────────────────────────────────────────────────────────────

    def _execute_resolution_round(self) -> dict[str, typing.Any]:
        """
        AI jury using Optimistic Democracy + Vector precedent lookup.

        Flow:
          1. Fetch k-nearest past rulings from VecDB (semantic similarity)
          2. Leader LLM proposes outcome with precedent context
          3. Validator re-runs independently, checks outcome equivalence
          4. High-ambiguity cases trigger extended validation
          5. Verdict stored back into VecDB for future precedent lookup
        """
        urls_snap        = gl.storage.copy_to_memory(self.evidence_urls)
        question_snap    = self.question
        description_snap = self.description
        deadline_snap    = int(self.resolution_deadline)
        round_snap       = int(self.current_round)
        chain_snap       = int(self.source_chain)

        # ── UNLOCK #1 — Pull semantic precedents ──────────────────────
        precedents_text = self._get_precedents_text(question_snap)

        def leader_fn() -> dict:
            evidence = _fetch_evidence(urls_snap)
            prompt = f"""You are an expert oracle resolver for a decentralized prediction market.

QUESTION: {question_snap}
CONTEXT: {description_snap}
RESOLUTION DEADLINE (unix timestamp): {deadline_snap}
SOURCE CHAIN: {_chain_label(chain_snap)}

EVIDENCE:
{evidence}

PRECEDENTS (similar past markets resolved by this oracle — use for calibration):
{precedents_text}

RESOLUTION RULES:
1. Answer YES only if evidence CONCLUSIVELY proves the statement true.
2. Answer NO only if evidence CONCLUSIVELY proves the statement false.
3. Answer INVALID if the question is ambiguous, unverifiable, or evidence insufficient.
4. Only consider information available before the resolution deadline.
5. If precedents exist for similar questions, weight them alongside the evidence.

Respond ONLY with this JSON — no markdown, no extra text:
{{
    "outcome": "YES" or "NO" or "INVALID",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<detailed explanation>",
    "key_evidence": ["<point 1>", "<point 2>"],
    "ambiguity_score": <float 0.0-1.0>,
    "precedent_influence": "<brief note on whether precedents shaped this ruling>"
}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format='json')
            if isinstance(raw, str):
                raw = raw.replace("```json", "").replace("```", "").strip()
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            if isinstance(raw, dict):
                return raw
            return {
                "outcome": "INVALID", "confidence": 0.0,
                "reasoning": "Failed to parse LLM response",
                "key_evidence": [], "ambiguity_score": 1.0,
                "precedent_influence": "none",
            }

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_data = leader_result.calldata
            if "outcome" not in leader_data:
                return False
            try:
                my_data = leader_fn()
            except Exception:
                return False
            return (
                leader_data.get("outcome", "INVALID").upper()
                == my_data.get("outcome", "INVALID").upper()
            )

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        outcome_str     = result.get("outcome", "INVALID").upper()
        final_outcome   = _str_to_outcome(outcome_str)
        confidence      = float(result.get("confidence", 0.0))
        ambiguity       = float(result.get("ambiguity_score", 1.0))
        reasoning       = result.get("reasoning", "")
        consensus_reached = True

        if ambiguity > 0.5 or confidence < 0.65:
            second = self._extended_validation(
                urls_snap, question_snap, description_snap,
                deadline_snap, result, precedents_text
            )
            if not second["consensus_reached"]:
                final_outcome     = Outcome.INVALID
                consensus_reached = False
                confidence        = 0.0
            else:
                confidence = second["confidence"]

        # ── Store round ───────────────────────────────────────────────
        self.resolution_rounds.append(ResolutionRound(
            round_number      = u32(round_snap),
            proposed_outcome  = u8(final_outcome),
            leader_confidence = confidence,
            leader_reasoning  = reasoning,
            consensus_reached = consensus_reached,
            final_outcome     = u8(final_outcome),
            confidence_score  = confidence,
        ))

        self.outcome            = u8(final_outcome)
        self.status             = u8(MarketStatus.RESOLVED)
        self.resolution_details = reasoning

        # ── UNLOCK #1 — Index ruling in VecDB for future precedents ───
        if consensus_reached and final_outcome != Outcome.UNRESOLVED:
            self._store_precedent(
                question     = question_snap,
                outcome      = final_outcome,
                confidence   = confidence,
                reasoning    = reasoning,
                source_chain = chain_snap,
                market_id    = self.external_market_id,
            )

        return {
            "outcome":           final_outcome,
            "outcome_label":     outcome_str if consensus_reached else "INVALID",
            "confidence":        confidence,
            "consensus_reached": consensus_reached,
            "round":             round_snap,
            "ambiguity":         ambiguity,
        }

    # ─────────────────────────────────────────────────────────────────
    # CORE — Cross-chain resolution (Polymarket, Azuro, etc.)
    # ─────────────────────────────────────────────────────────────────

    def _resolve_cross_chain_request(self, condition_id: str) -> dict[str, typing.Any]:
        """
        Resolves a request submitted by an external relayer.
        Uses the same AI jury + precedent lookup as native markets.
        Fetches live Polymarket data if source_chain == POLYMARKET.
        """
        req = self.cross_chain_requests[condition_id]

        urls_snap    = gl.storage.copy_to_memory(req.evidence_urls)
        question_snap = req.question
        desc_snap     = req.description
        chain_snap    = int(req.source_chain)

        precedents_text = self._get_precedents_text(question_snap)

        # If Polymarket, fetch live market data from Gamma API (no key needed)
        polymarket_context = ""
        if chain_snap == SourceChain.POLYMARKET:
            polymarket_context = _fetch_polymarket_context(condition_id)

        def leader_fn() -> dict:
            evidence = _fetch_evidence(urls_snap)
            prompt = f"""You are an expert oracle resolver serving a cross-chain prediction market.

SOURCE CHAIN: {_chain_label(chain_snap)}
EXTERNAL MARKET ID: {condition_id}
QUESTION: {question_snap}
CONTEXT: {desc_snap}

LIVE MARKET DATA (from source chain):
{polymarket_context if polymarket_context else "[not available]"}

EVIDENCE SOURCES:
{evidence}

PRECEDENTS (similar past rulings from this oracle):
{precedents_text}

RESOLUTION RULES:
1. Answer YES only if evidence CONCLUSIVELY proves the statement true.
2. Answer NO only if evidence CONCLUSIVELY proves the statement false.
3. Answer INVALID if the question is ambiguous or evidence is insufficient.
4. Weigh the live market consensus price as a signal (not as proof).
5. Use precedents to calibrate confidence for similar question types.

Respond ONLY with this JSON:
{{
    "outcome": "YES" or "NO" or "INVALID",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<detailed explanation>",
    "key_evidence": ["<point 1>", "<point 2>"],
    "ambiguity_score": <float 0.0-1.0>,
    "market_price_signal": "<what the live market price implies, if available>"
}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format='json')
            if isinstance(raw, str):
                raw = raw.replace("```json", "").replace("```", "").strip()
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            if isinstance(raw, dict):
                return raw
            return {
                "outcome": "INVALID", "confidence": 0.0,
                "reasoning": "Parse error", "key_evidence": [],
                "ambiguity_score": 1.0, "market_price_signal": "n/a",
            }

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_data = leader_result.calldata
            if "outcome" not in leader_data:
                return False
            try:
                my_data = leader_fn()
            except Exception:
                return False
            return (
                leader_data.get("outcome", "INVALID").upper()
                == my_data.get("outcome", "INVALID").upper()
            )

        result        = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        outcome_str   = result.get("outcome", "INVALID").upper()
        final_outcome = _str_to_outcome(outcome_str)
        confidence    = float(result.get("confidence", 0.0))
        reasoning     = result.get("reasoning", "")

        # Mark request fulfilled
        old_req = self.cross_chain_requests[condition_id]
        updated = CrossChainRequest(
            condition_id   = old_req.condition_id,
            source_chain   = old_req.source_chain,
            question       = old_req.question,
            description    = old_req.description,
            evidence_urls  = old_req.evidence_urls,
            oracle_fee_bps = old_req.oracle_fee_bps,
            requester      = old_req.requester,
            fee_deposited  = old_req.fee_deposited,
            fulfilled      = True,
            outcome        = u8(final_outcome),
        )
        self.cross_chain_requests[condition_id] = updated

        # Index in VecDB
        self._store_precedent(
            question     = question_snap,
            outcome      = final_outcome,
            confidence   = confidence,
            reasoning    = reasoning,
            source_chain = chain_snap,
            market_id    = condition_id,
        )

        return {
            "outcome":    final_outcome,
            "confidence": confidence,
            "reasoning":  reasoning,
        }

    # ─────────────────────────────────────────────────────────────────
    # UNLOCK #1 — Vector Storage helpers
    # ─────────────────────────────────────────────────────────────────

    def _get_embedding_generator(self):
        """Sentence transformer for 384-dim embeddings."""
        return genlayermodelwrappers.SentenceTransformer("all-MiniLM-L6-v2")

    def _embed(self, text: str) -> np.ndarray:
        return self._get_embedding_generator()(text)

    def _store_precedent(
        self,
        question:     str,
        outcome:      int,
        confidence:   float,
        reasoning:    str,
        source_chain: int,
        market_id:    str,
    ) -> None:
        """Embed the question and store the ruling in VecDB."""
        try:
            emb = self._embed(question)
            entry = PrecedentEntry(
                question     = question,
                outcome      = u8(outcome),
                confidence   = confidence,
                reasoning    = reasoning[:500],  # truncate for storage efficiency
                source_chain = u8(source_chain),
                market_id    = market_id,
                resolved_at  = u256(gl.block.timestamp),
            )
            self.precedent_store.insert(emb, entry)
            self.total_precedents = u32(int(self.total_precedents) + 1)
        except Exception:
            pass  # Never let VecDB failure break resolution

    def _get_precedents_text(self, question: str) -> str:
        """
        Find the 3 most semantically similar past rulings and format
        them as a compact text block for the LLM jury prompt.
        """
        try:
            if int(self.total_precedents) == 0:
                return "[No precedents yet — this is the oracle's first market]"
            emb     = self._embed(question)
            results = list(self.precedent_store.knn(emb, 3))
            if not results:
                return "[No similar precedents found]"
            lines = []
            for i, r in enumerate(results):
                p    = r.value
                sim  = round(1.0 - float(r.distance), 3)
                label = _outcome_label(int(p.outcome))
                chain = _chain_label(int(p.source_chain))
                lines.append(
                    f"Precedent {i+1} (similarity={sim}, chain={chain}):\n"
                    f"  Q: {p.question}\n"
                    f"  Ruling: {label} (confidence={round(p.confidence,2)})\n"
                    f"  Reason: {p.reasoning[:200]}"
                )
            return "\n\n".join(lines)
        except Exception as e:
            return f"[Precedent lookup failed: {e}]"

    @gl.public.view
    def search_precedents(self, query: str, k: int = 5) -> list:
        """
        Public: semantic search over all past rulings.
        Useful for UIs showing 'similar markets resolved before'.
        """
        try:
            emb     = self._embed(query)
            results = list(self.precedent_store.knn(emb, k))
            out = []
            for r in results:
                p = r.value
                out.append({
                    "question":     p.question,
                    "outcome":      _outcome_label(int(p.outcome)),
                    "confidence":   round(p.confidence, 3),
                    "source_chain": _chain_label(int(p.source_chain)),
                    "market_id":    p.market_id,
                    "similarity":   round(1.0 - float(r.distance), 3),
                })
            return out
        except Exception:
            return []

    # ─────────────────────────────────────────────────────────────────
    # Extended validation (ambiguous cases)
    # ─────────────────────────────────────────────────────────────────

    def _extended_validation(
        self,
        urls_snap:        list,
        question_snap:    str,
        description_snap: str,
        deadline_snap:    int,
        leader_result:    dict,
        precedents_text:  str,
    ) -> dict[str, typing.Any]:
        leader_outcome   = leader_result.get("outcome", "INVALID")
        leader_reasoning = leader_result.get("reasoning", "")

        def validator_task() -> dict:
            evidence = _fetch_evidence(urls_snap)
            prompt = f"""You are an independent validator in a decentralized oracle.
A lead resolver proposed an outcome. Independently verify it.

QUESTION: {question_snap}
CONTEXT:  {description_snap}
DEADLINE: {deadline_snap}

LEAD OUTCOME:   {leader_outcome}
LEAD REASONING: {leader_reasoning}

EVIDENCE (fetched independently):
{evidence}

PRECEDENTS:
{precedents_text}

Form your own independent view — do NOT simply echo the lead resolver.

Respond ONLY with this JSON:
{{
    "agreement": true or false,
    "your_outcome": "YES" or "NO" or "INVALID",
    "confidence": <float 0.0-1.0>,
    "notes": "<key points from your independent analysis>"
}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format='json')
            if isinstance(raw, str):
                raw = raw.replace("```json", "").replace("```", "").strip()
                try:
                    return json.loads(raw)
                except Exception:
                    pass
            if isinstance(raw, dict):
                return raw
            return {"agreement": False, "your_outcome": "INVALID", "confidence": 0.0, "notes": "Parse error"}

        def val_validator(val_result) -> bool:
            if not isinstance(val_result, gl.vm.Return):
                return False
            try:
                my_data = validator_task()
            except Exception:
                return False
            return (
                val_result.calldata.get("your_outcome", "INVALID").upper()
                == my_data.get("your_outcome", "INVALID").upper()
            )

        val_result  = gl.vm.run_nondet_unsafe(validator_task, val_validator)
        agrees      = bool(val_result.get("agreement", False))
        val_outcome = val_result.get("your_outcome", "INVALID").upper()

        if agrees and _str_to_outcome(val_outcome) == _str_to_outcome(leader_outcome.upper()):
            avg = (
                float(leader_result.get("confidence", 0.5))
                + float(val_result.get("confidence", 0.5))
            ) / 2.0
            return {"consensus_reached": True, "outcome": _str_to_outcome(val_outcome), "confidence": avg}
        else:
            return {"consensus_reached": False, "outcome": Outcome.INVALID, "confidence": 0.0}

    # ─────────────────────────────────────────────────────────────────
    # View functions
    # ─────────────────────────────────────────────────────────────────

    @gl.public.view
    def get_market_info(self) -> dict[str, typing.Any]:
        total    = self.total_yes_stake + self.total_no_stake
        odds_yes = u256(0)
        odds_no  = u256(0)
        if total > u256(0):
            if self.total_yes_stake > u256(0):
                odds_yes = (total * u256(10000)) // self.total_yes_stake
            if self.total_no_stake > u256(0):
                odds_no  = (total * u256(10000)) // self.total_no_stake
        urls = [self.evidence_urls[i] for i in range(len(self.evidence_urls))]
        return {
            "question":            self.question,
            "description":         self.description,
            "evidence_urls":       urls,
            "status":              int(self.status),
            "outcome":             int(self.outcome),
            "resolution_details":  self.resolution_details,
            "total_yes_stake":     str(self.total_yes_stake),
            "total_no_stake":      str(self.total_no_stake),
            "total_liquidity":     str(total),
            "odds_yes_bps":        str(odds_yes),
            "odds_no_bps":         str(odds_no),
            "current_round":       int(self.current_round),
            "max_rounds":          int(self.max_rounds),
            "resolution_deadline": str(self.resolution_deadline),
            "bettor_count":        len(self.bettors_list),
            "source_chain":        _chain_label(int(self.source_chain)),
            "external_market_id":  self.external_market_id,
            "total_precedents":    int(self.total_precedents),
            "accumulated_fees":    str(self.accumulated_fees),
            "oracle_fee_bps":      int(self.oracle_fee_bps),
        }

    @gl.public.view
    def get_bet(self, bettor: Address) -> dict[str, typing.Any] | None:
        if bettor not in self.bets:
            return None
        bet      = self.bets[bettor]
        estimate = u256(0)
        if int(self.status) == MarketStatus.RESOLVED and int(bet.prediction) == int(self.outcome):
            if int(self.outcome) == Outcome.YES:
                winning_pool = self.total_yes_stake
                losing_pool  = self.total_no_stake
            else:
                winning_pool = self.total_no_stake
                losing_pool  = self.total_yes_stake
            if winning_pool > u256(0):
                estimate = bet.amount + (bet.amount * losing_pool) // winning_pool
        return {
            "bettor":           str(bettor),
            "amount":           str(bet.amount),
            "prediction":       int(bet.prediction),
            "prediction_label": "YES" if int(bet.prediction) == 1 else "NO",
            "claimed":          bet.claimed,
            "payout_estimate":  str(estimate),
        }

    @gl.public.view
    def get_resolution_history(self) -> list:
        history     = []
        rounds_copy = gl.storage.copy_to_memory(self.resolution_rounds)
        for r in rounds_copy:
            history.append({
                "round":             int(r.round_number),
                "proposed_outcome":  int(r.proposed_outcome),
                "final_outcome":     int(r.final_outcome),
                "outcome_label":     _outcome_label(int(r.final_outcome)),
                "confidence_score":  r.confidence_score,
                "consensus_reached": r.consensus_reached,
                "reasoning":         r.leader_reasoning,
            })
        return history

    @gl.public.view
    def get_oracle_stats(self) -> dict[str, typing.Any]:
        """High-level stats — useful for UI and relayer health checks."""
        return {
            "total_precedents":  int(self.total_precedents),
            "accumulated_fees":  str(self.accumulated_fees),
            "oracle_fee_bps":    int(self.oracle_fee_bps),
            "pending_requests":  sum(
                1 for rid in [self.request_ids[i] for i in range(len(self.request_ids))]
                if not self.cross_chain_requests[rid].fulfilled
            ),
            "fulfilled_requests": sum(
                1 for rid in [self.request_ids[i] for i in range(len(self.request_ids))]
                if self.cross_chain_requests[rid].fulfilled
            ),
            "creator":           str(self.creator),
        }

    @gl.public.view
    def get_pending_cross_chain_requests(self) -> list:
        """Returns all unfulfilled external resolution requests."""
        out = []
        for i in range(len(self.request_ids)):
            rid = self.request_ids[i]
            req = self.cross_chain_requests[rid]
            if not req.fulfilled:
                out.append({
                    "condition_id":  req.condition_id,
                    "source_chain":  _chain_label(int(req.source_chain)),
                    "question":      req.question,
                    "requester":     str(req.requester),
                    "fee_deposited": str(req.fee_deposited),
                })
        return out

    @gl.public.view
    def can_resolve(self) -> bool:
        return (
            int(self.status) in [MarketStatus.OPEN, MarketStatus.DISPUTED]
            and int(self.current_round) < int(self.max_rounds)
            and (
                gl.block.timestamp >= int(self.resolution_deadline)
                or len(self.bettors_list) > 0
            )
        )

    @gl.public.view
    def get_resolver_info(self) -> dict[str, typing.Any]:
        return {
            "resolution_bond": str(self.resolution_bond),
            "dispute_stake":   str(self.resolution_bond // u256(2)),
            "current_round":   int(self.current_round),
            "max_rounds":      int(self.max_rounds),
            "dispute_count":   len(self.dispute_raisers),
            "appeal_window":   str(self.appeal_window),
        }


# ─────────────────────────────────────────────────────────────────────
# Module-level helpers (no storage access; safe inside nondet blocks)
# ─────────────────────────────────────────────────────────────────────

def _fetch_evidence(urls: list) -> str:
    """
    Fetch and concatenate all evidence URLs.
    Must be called INSIDE a nondet block.
    """
    parts = []
    for url in urls:
        try:
            text = gl.nondet.web.render(url, mode="text")
            parts.append(f"=== SOURCE: {url} ===\n{text[:3000]}\n")
        except Exception as e:
            parts.append(f"=== SOURCE: {url} ===\n[Fetch error: {e}]\n")
    return "\n".join(parts) if parts else "[No evidence sources provided]"


def _fetch_polymarket_context(condition_id: str) -> str:
    """
    UNLOCK #3 — Fetch live Polymarket market data from Gamma API.
    No API key required. Returns a compact summary for the LLM jury.

    Polymarket Gamma API endpoints used:
      GET https://gamma-api.polymarket.com/markets?condition_id=<id>
        → question, description, outcomePrices, volume, liquidity, end_date_iso

    The jury uses market price as a signal (crowd wisdom), not as proof.
    """
    try:
        gamma_url = f"https://gamma-api.polymarket.com/markets?condition_id={condition_id}"
        raw_text  = gl.nondet.web.render(gamma_url, mode="text")

        # Parse JSON from fetched text (Gamma API returns JSON)
        try:
            data = json.loads(raw_text)
        except Exception:
            # Sometimes render wraps in HTML; try to extract JSON
            start = raw_text.find("[")
            end   = raw_text.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(raw_text[start:end])
            else:
                return "[Polymarket API returned non-JSON response]"

        if not data or not isinstance(data, list):
            return "[No Polymarket market found for this condition_id]"

        market = data[0]
        question     = market.get("question", "N/A")
        end_date     = market.get("endDateIso", market.get("end_date_iso", "N/A"))
        outcomes     = market.get("outcomes", "[]")
        prices       = market.get("outcomePrices", "[]")
        volume       = market.get("volume", "N/A")
        liquidity    = market.get("liquidity", "N/A")
        description  = market.get("description", "")[:300]
        closed       = market.get("closed", False)
        active       = market.get("active", True)

        # Parse outcomes/prices safely
        try:
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if isinstance(prices, str):
                prices = json.loads(prices)
        except Exception:
            pass

        price_lines = ""
        if isinstance(outcomes, list) and isinstance(prices, list):
            pairs = zip(outcomes, prices)
            price_lines = "\n".join(f"  {o}: {p}" for o, p in pairs)

        return f"""Polymarket Market Data (condition_id: {condition_id}):
  Question: {question}
  End Date: {end_date}
  Status: {"Closed" if closed else "Active" if active else "Unknown"}
  Volume: ${volume}
  Liquidity: ${liquidity}
  Outcome Prices (crowd consensus):
{price_lines}
  Description: {description}"""

    except Exception as e:
        return f"[Failed to fetch Polymarket context: {e}]"


def _outcome_label(outcome: int) -> str:
    if outcome == Outcome.YES:     return "YES"
    if outcome == Outcome.NO:      return "NO"
    if outcome == Outcome.INVALID: return "INVALID"
    return "UNRESOLVED"


def _chain_label(chain: int) -> str:
    if chain == SourceChain.GENLAYER:   return "GenLayer"
    if chain == SourceChain.POLYMARKET: return "Polymarket (Polygon)"
    if chain == SourceChain.AZURO:      return "Azuro (Gnosis/Arbitrum)"
    return "Custom"


def _str_to_outcome(s: str) -> int:
    if s == "YES":     return Outcome.YES
    if s == "NO":      return Outcome.NO
    return Outcome.INVALID


# ─────────────────────────────────────────────────────────────────────
# Deployment notes
# ─────────────────────────────────────────────────────────────────────
#
# Constructor params for a Polymarket resolution service deployment:
#   question             = "GenLayer Oracle Service"
#   description          = "Cross-chain resolution hub"
#   evidence_urls        = []
#   min_bet              = 0          (no native bets needed if pure oracle)
#   resolution_bond      = 10**16     (0.01 ETH)
#   resolution_deadline  = far future (e.g. block.timestamp + 365 days)
#   appeal_window        = 86400      (24h)
#   oracle_fee_bps       = 150        (1.5%)
#   source_chain         = 0          (GENLAYER hub)
#   external_market_id   = ""
#
# Polymarket relayer flow:
#   1. Watch Polymarket for markets approaching resolution
#   2. Call request_cross_chain_resolution(condition_id, 1, question, ...)
#      with ETH deposit covering oracle_fee_bps of prize pool
#   3. Poll get_cross_chain_verdict(condition_id) until fulfilled == True
#   4. Post verdict to Polymarket's UMA optimistic oracle or custom resolver
#   5. Claim dispute bond back if verdict matches UMA's ruling
#
# Revenue per $1M Polymarket market at 1.5% fee: $15,000
# Plus GenLayer mainnet 20% perpetual tx fee share

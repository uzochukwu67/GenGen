/**
 * relayer-keeper.js — GenLayer Oracle Hub Keeper/Relayer (Node.js)
 * ============================================================
 *
 * WHAT THIS DOES:
 *   1. Watches the GenLayer Oracle Hub for pending markets past their deadline
 *   2. Calls trigger_resolution() on GenLayer to start the AI jury
 *   3. Polls for resolved verdicts
 *   4. Posts verdicts back to EVM chains via OracleConsumer.receiveVerdict()
 *   5. Calls confirm_callback() on GenLayer to mark delivery complete
 *
 * This is the "bridge" between GenLayer and EVM chains.
 * For production: replace with LayerZero/Axelar for trustless delivery.
 * For hackathon demo: this script + a testnet wallet is all you need.
 *
 * SETUP:
 *   npm install genlayer-js ethers dotenv
 *
 * ENV VARS (.env):
 *   GENLAYER_RPC=https://studio.genlayer.com
 *   HUB_ADDRESS=0x5286D78605d6D255A2FfF4911cC57ef35692e461
 *   EVM_RPC_POLYGON_AMOY=https://rpc-amoy.polygon.technology
 *   RELAYER_PRIVATE_KEY=0x...
 *   POLL_INTERVAL_SECONDS=30
 */

const { createClient } = require('genlayer-js');
const { privateKeyToAccount } = require('viem/accounts');
const ethers = require('ethers');
require('dotenv').config();

// ─────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────

const GENLAYER_RPC = process.env.GENLAYER_RPC || 'https://studio.genlayer.com';
const HUB_ADDRESS = process.env.HUB_ADDRESS || process.env.ORACLE_HUB_CONTRACT_ADDRESS || '';
const PRIVATE_KEY = process.env.RELAYER_PRIVATE_KEY || '';
const POLL_INTERVAL = parseInt(process.env.POLL_INTERVAL_SECONDS || '30');

// Create viem account from private key
const account = PRIVATE_KEY ? privateKeyToAccount(PRIVATE_KEY) : null;
if (PRIVATE_KEY) {
  console.log('🔑 Relayer account:', account?.address);
}

// EVM chain configs: chain_key → {rpc, consumer_address}
const EVM_CHAINS = {
  'polygon-amoy-v1': {
    rpc: process.env.EVM_RPC_POLYGON_AMOY || 'https://rpc-amoy.polygon.technology',
    consumer: process.env.CONSUMER_POLYGON || '',
    chainId: 80002,
  },
  'ethereum-mainnet': {
    rpc: process.env.EVM_RPC_ETH || '',
    consumer: process.env.CONSUMER_ETH || '',
    chainId: 1,
  },
  'base-mainnet': {
    rpc: process.env.EVM_RPC_BASE || '',
    consumer: process.env.CONSUMER_BASE || '',
    chainId: 8453,
  },
};

// OracleConsumer ABI (just the functions we need)
const CONSUMER_ABI = [
  {
    inputs: [
      { name: 'marketId', type: 'string' },
      { name: 'outcome', type: 'uint8' },
      { name: 'confidence', type: 'uint256' },
      { name: 'reasoning', type: 'string' },
    ],
    name: 'receiveVerdict',
    outputs: [],
    stateMutability: 'nonpayable',
    type: 'function',
  },
  {
    inputs: [{ name: 'marketId', type: 'string' }],
    name: 'getMarket',
    outputs: [
      { name: 'question', type: 'string' },
      { name: 'state', type: 'uint8' },
      { name: 'outcome', type: 'uint8' },
      { name: 'yesPool', type: 'uint256' },
      { name: 'noPool', type: 'uint256' },
      { name: 'deadline', type: 'uint256' },
      { name: 'confidence', type: 'uint256' },
      { name: 'verdictReceived', type: 'bool' },
    ],
    stateMutability: 'view',
    type: 'function',
  },
];

// ─────────────────────────────────────────────
// Core keeper logic
// ─────────────────────────────────────────────

class OracleKeeper {
  constructor() {
    this.gl = createClient({
      endpoint: GENLAYER_RPC,
      account: account
    });
    this.providers = {}; // chain_key → ethers.Provider
    this.signers = {};   // chain_key → ethers.Signer
    this.processed = new Set(); // market_ids already delivered

    // Bootstrap ethers connections for each known EVM chain
    for (const [chainKey, cfg] of Object.entries(EVM_CHAINS)) {
      if (!cfg.rpc || !cfg.consumer) continue;

      const provider = new ethers.JsonRpcProvider(cfg.rpc);
      const signer = new ethers.Wallet(PRIVATE_KEY, provider);

      this.providers[chainKey] = provider;
      this.signers[chainKey] = signer;

      console.log(`✅ Connected to ${chainKey}`);
    }
  }

  async run() {
    console.log('🚀 Relayer keeper started.');
    while (true) {
      try {
        await this._tick();
      } catch (error) {
        console.error('❌ Tick error:', error.message);
      }
      await this._sleep(POLL_INTERVAL * 1000);
    }
  }

  async _tick() {
    // 1. Get hub stats
    const hubStats = await this._hubCall('get_hub_stats');
    console.log('🔍 Raw hub stats response:', JSON.stringify(hubStats, null, 2));
    console.log(`📊 Hub: ${hubStats?.total_chains || 'N/A'} chains, ${hubStats?.total_markets || 'N/A'} markets, ${hubStats?.total_resolved || 'N/A'} resolved`);

    // 2. For each configured chain, verify registration then check markets
    for (const chainKey of Object.keys(EVM_CHAINS)) {
      const chainInfo = await this._hubCall('get_chain', { chain_key: chainKey });
      if (!chainInfo || chainInfo === null || Object.keys(chainInfo).length === 0) {
        console.log(`🚫 Chain not registered or not found: ${chainKey}`);
        continue;
      }

      console.log(`✅ Registered chain found: ${chainKey} (active=${chainInfo.active})`);
      await this._processChain(chainKey);
    }
  }

  async _processChain(chainKey) {
    const markets = await this._hubCall('get_markets_for_chain', { chain_key: chainKey });
    console.log(`🔍 Raw markets response for ${chainKey}:`, JSON.stringify(markets, null, 2));

    if (!markets || markets === null) {
      console.log(`⚠️ No markets data for ${chainKey}, skipping`);
      return;
    }

    const marketsArray = Array.isArray(markets)
      ? markets
      : (markets && Array.isArray(markets.markets) ? markets.markets : []);

    if (marketsArray.length === 0) {
      console.log(`📭 No markets for ${chainKey}`);
      return;
    }

    for (const market of marketsArray) {
      const marketId = market.market_id;
      const state = market.state;

      if (this.processed.has(marketId)) continue;

      if (state === 'PENDING') {
        // Try to trigger resolution (hub will reject if deadline not met)
        try {
          const result = await this._hubWrite('trigger_resolution', { market_id: marketId });
          console.log(`🎯 Triggered resolution for ${marketId}:`, result);
        } catch (error) {
          console.debug(`⏳ Cannot trigger ${marketId} yet:`, error.message);
        }
      } else if (state === 'RESOLVED') {
        // Read verdict and post to source chain
        const verdict = await this._hubCall('get_verdict', { market_id: marketId });
        if (verdict && !verdict.callback_posted) {
          await this._deliverVerdict(chainKey, verdict);
        }
      }
    }
  }

  async _deliverVerdict(chainKey, verdict) {
    const marketId = verdict.market_id;
    const externalId = verdict.external_id;
    const outcomeInt = verdict.outcome_int; // 1=YES, 2=NO, 3=INVALID
    const confidence = Math.floor(verdict.confidence * 1000); // scale to 0-1000
    const reasoning = verdict.reasoning.substring(0, 500);

    console.log(`📤 Delivering verdict for ${marketId}: outcome=${verdict.outcome} conf=${confidence}`);

    // Post to EVM chain
    const delivered = await this._postToEvm(chainKey, marketId, outcomeInt, confidence, reasoning);

    if (delivered) {
      // Confirm delivery on GenLayer
      try {
        await this._hubWrite('confirm_callback', { market_id: marketId });
        this.processed.add(marketId);
        console.log(`✅ Verdict delivered and confirmed: ${marketId}`);
      } catch (error) {
        console.error(`❌ Failed to confirm callback for ${marketId}:`, error.message);
      }
    } else {
      console.warn(`⚠️ Failed to deliver verdict for ${marketId} to ${chainKey}`);
    }
  }

  async _postToEvm(chainKey, marketId, outcome, confidence, reasoning) {
    if (!(chainKey in this.signers)) {
      console.warn(`⚠️ No ethers connection for ${chainKey}`);
      return await this._postViaHttpCallback(chainKey, marketId, outcome, confidence, reasoning);
    }

    const cfg = EVM_CHAINS[chainKey];
    const signer = this.signers[chainKey];

    try {
      const consumer = new ethers.Contract(cfg.consumer, CONSUMER_ABI, signer);

      const tx = await consumer.receiveVerdict(marketId, outcome, confidence, reasoning, {
        gasLimit: 200000,
      });

      const receipt = await tx.wait();
      if (receipt.status === 1) {
        console.log(`🔗 EVM callback tx: ${receipt.hash} on ${chainKey}`);
        return true;
      } else {
        console.error(`❌ EVM tx failed: ${receipt.hash}`);
        return false;
      }
    } catch (error) {
      console.error(`❌ EVM post error for ${chainKey}:`, error.message);
      return false;
    }
  }

  async _postViaHttpCallback(chainKey, marketId, outcome, confidence, reasoning) {
    /**
     * Fallback for RELAYER adapter type: POST verdict to callback_url.
     * The receiving server is responsible for posting to the chain.
     */
    try {
      const chain = await this._hubCall('get_chain', { chain_key: chainKey });
      if (!chain || !chain.callback_url) return false;

      const payload = JSON.stringify({
        market_id: marketId,
        outcome: outcome,
        confidence: confidence,
        reasoning: reasoning,
      });

      const response = await fetch(chain.callback_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
      });

      return response.ok;
    } catch (error) {
      console.error('❌ HTTP callback error:', error.message);
      return false;
    }
  }

  // ── GenLayer SDK helpers ──────────────────────────────────────────

  async _hubCall(method, params = {}) {
    /** Read-only call to GenLayer Hub. */
    let result;
    try {
      result = await this.gl.call(HUB_ADDRESS, method, params);
      if (result && typeof result === 'object' && Object.keys(result).length === 0) {
        throw new Error('Empty object returned, try readContract fallback');
      }
      return result;
    } catch (callError) {
      console.warn(`⚠️ gl.call failed for ${method}: ${callError.message}, trying readContract fallback`);

      const readArgs = [];
      if (method === 'get_chain' || method === 'get_markets_for_chain') {
        if (params.chain_key) readArgs.push(params.chain_key);
      } else if (method === 'get_verdict') {
        if (params.market_id) readArgs.push(params.market_id);
      }

      try {
        const fallback = await this.gl.readContract({
          address: HUB_ADDRESS,
          functionName: method,
          args: readArgs,
        });
        return fallback;
      } catch (readError) {
        console.error(`❌ readContract fallback failed for ${method}:`, readError.message);
        throw callError;
      }
    }
  }

  async _hubWrite(method, params = {}) {
    /** State-changing call to GenLayer Hub. */
    return await this.gl.sendTransaction(HUB_ADDRESS, method, params, {
      // account already provided in client
    });
  }

  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ─────────────────────────────────────────────
// Example: how a chain registers and creates a market
// (run this once to set up; keeper handles the rest)
// ─────────────────────────────────────────────

const EXAMPLE_REGISTRATION = `
Example — register Polygon Amoy with the hub:

const { createClient } = require('genlayer-js');
const gl = createClient({ endpoint: GENLAYER_RPC });

// 1. Register
await gl.sendTransaction(HUB_ADDRESS, 'register_chain', {
  chain_key: 'polygon-amoy-v1',
  chain_type: 0,           // EVM
  adapter_type: 3,         // RELAYER (keeper script)
  adapter_address: '0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79',
  callback_url: 'https://your-keeper.example.com/verdict',
  metadata: JSON.stringify({
    chain_id: 80002,
    rpc_url: 'https://rpc-amoy.polygon.technology',
    contract: '0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79',
    market_api_url: 'https://testnet.gamma-api.polymarket.com/markets',
  }),
  fee_bps: 0,  // use global rate
}, { privateKey: YOUR_KEY, value: MIN_STAKE });

// 2. Create a market
await gl.sendTransaction(HUB_ADDRESS, 'create_market', {
  chain_key: 'polygon-amoy-v1',
  external_id: '0xabc123',      // Test market ID
  question: 'Will ETH exceed $5000 by end of 2024?',
  description: 'Binary prediction market on Ethereum price',
  resolution_criteria: 'YES if Coinbase spot ETH/USD ≥ $5,000 at any point before deadline. NO otherwise.',
  evidence_urls: [
    'https://api.coinbase.com/v2/prices/ETH-USD/spot',
    'https://testnet.gamma-api.polymarket.com/markets?condition_id=0xabc123',
  ],
  deadline: 1735689600,  // unix timestamp
  prize_pool_proxy: 10000,       // $10k test pool
}, { privateKey: YOUR_KEY, value: ORACLE_FEE });

// Keeper picks it up and does the rest automatically.
`;

// ─────────────────────────────────────────────
// Main execution
// ─────────────────────────────────────────────

if (require.main === module) {
  const keeper = new OracleKeeper();
  keeper.run().catch(console.error);
}

module.exports = { OracleKeeper };
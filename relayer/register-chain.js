/**
 * register-chain.js — Register Polygon Amoy with GenLayer Oracle Hub
 * ================================================================
 *
 * This script registers Polygon Amoy testnet with the GenLayer Oracle Hub
 * so the relayer can monitor and deliver verdicts to it.
 *
 * SETUP:
 *   npm install genlayer-js dotenv viem
 *
 * ENV VARS (.env):
 *   RELAYER_PRIVATE_KEY=0x... (your wallet private key)
 *   HUB_ADDRESS=0xDF079d367bc9a00401AC8777bDF3610B4015e196
 */

const { createClient, createAccount } = require('genlayer-js');
const { studionet } = require('genlayer-js/chains');
const { TransactionStatus, ExecutionResult } = require('genlayer-js/types');
const { privateKeyToAccount } = require('viem/accounts');
const { parseEther } = require('viem');
require('dotenv').config();

// ─────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────

const HUB_ADDRESS = process.env.HUB_ADDRESS || '0xDF079d367bc9a00401AC8777bDF3610B4015e196';
const PRIVATE_KEY = process.env.RELAYER_PRIVATE_KEY || '';

if (!PRIVATE_KEY) {
  console.error('❌ RELAYER_PRIVATE_KEY not set in .env');
  process.exit(1);
}

// Create account from private key
const account = privateKeyToAccount(PRIVATE_KEY);
console.log('🔑 Using account:', account.address);

// ─────────────────────────────────────────────
// Chain Registration Data
// ─────────────────────────────────────────────

const POLYGON_AMOY_CONFIG = {
  chain_key: 'polygon-amoy-v1',
  chain_type: 0,           // EVM
  adapter_type: 3,         // RELAYER (keeper script)
  adapter_address: '0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79', // OracleConsumer contract
  callback_url: '',        // Empty for RELAYER adapter type
  metadata: JSON.stringify({
    chain_id: 80002,
    rpc_url: 'https://rpc-amoy.polygon.technology',
    contract: '0x126A93Ec7C25eEd3d2e9CFe6Aa9D81A62d840E79',
    market_api_url: 'https://testnet.gamma-api.polymarket.com/markets',
  }),
  fee_bps: 0,  // Use global rate
};

// Minimum stake: 10 GLN for instant approval (stake >= min_stake * 10)
const STAKE_AMOUNT = BigInt(process.env.STAKE_AMOUNT || parseEther('10').toString());

// ─────────────────────────────────────────────
// Registration Script
// ─────────────────────────────────────────────

async function registerChain() {
  console.log('🚀 Registering Polygon Amoy with GenLayer Oracle Hub...');

  // Create GenLayer client with viem account in read/write mode
  const gl = createClient({
    endpoint: GENLAYER_RPC,
    account: account,
  });

  try {
    console.log('💰 Ensure your wallet has enough GEN tokens for network fees and stake.');
    console.log('   Faucet: https://studio.genlayer.com/faucet');

    // Register the chain
    const chosenStake = process.env.STAKE ? ethers.BigNumber.from(process.env.STAKE) : HIGH_STAKE; // default 10 GLN
    console.log('📝 Sending register_chain transaction (write op) with required data and stake:', chosenStake.toString());
    const txHash = await gl.sendTransaction(HUB_ADDRESS, 'register_chain', POLYGON_AMOY_CONFIG, {
      value: chosenStake,
    });

    console.log('🔗 Transaction hash:', txHash);

    // Wait for transaction to be accepted or finalized
    console.log('⏳ Waiting for transaction receipt...');
    const receipt = await gl.waitForTransactionReceipt({
      hash: txHash,
      status: 'ACCEPTED',
      timeout: 120_000,
      interval: 3_000,
    });

    console.log('📜 Receipt:', JSON.stringify(receipt, null, 2));

    if (!receipt || (receipt.result_name && receipt.result_name !== 'SUCCESS')) {
      console.log('❌ Registration transaction did not reach SUCCESS (result_name=' + receipt?.result_name + ').');
      console.log('   It may still be in networking “NO_MAJORITY” finalization; retry or wait and re-check state.');
    } else {
      console.log('✅ Chain registration transaction appears successful.');
    }

    console.log('📍 Chain key: polygon-amoy-v1');
    console.log('🎯 Consumer contract:', POLYGON_AMOY_CONFIG.adapter_address);

    // Verify registration by checking if our specific chain exists
    console.log('🔍 Verifying registration using get_chain...');
    const chainInfo = await gl.call(HUB_ADDRESS, 'get_chain', { chain_key: 'polygon-amoy-v1' });
    console.log('📋 get_chain response:', JSON.stringify(chainInfo, null, 2));

    if (!chainInfo || Object.keys(chainInfo).length === 0) {
      console.log('🔁 Attempting fallback readContract call for get_chain...');
      try {
        const fallbackChainInfo = await gl.readContract({
          address: HUB_ADDRESS,
          functionName: 'get_chain',
          args: ['polygon-amoy-v1'],
        });
        console.log('📋 readContract(get_chain) response:', JSON.stringify(fallbackChainInfo, null, 2));
      } catch (readError) {
        console.log('⚠️ readContract fallback failed:', readError.message || readError);
      }
    }
    
    if (chainInfo && chainInfo.chain_key === 'polygon-amoy-v1') {
      console.log('✅ Verification successful!');
      console.log('📊 Registered chain:', JSON.stringify(chainInfo, null, 2));
    } else {
      console.log('⚠️ Could not verify registration (chain not found), but registration may have succeeded');
    }

  } catch (error) {
    console.error('❌ Registration failed:', error.message);
    console.error('Full error:', error);

    if (error.message.includes('insufficient funds') || error.message.includes('gas')) {
      console.log('💡 You need GEN tokens. Get some from the faucet:');
      console.log('   https://studio.genlayer.com/faucet');
      console.log('   Or run local GenLayer Studio and get tokens there');
    } else if (error.message.includes('already registered')) {
      console.log('ℹ️  Chain might already be registered. Check with: npm run check');
    }
  }
}

// ─────────────────────────────────────────────
// Main execution
// ─────────────────────────────────────────────

if (require.main === module) {
  registerChain().catch(console.error);
}

module.exports = { registerChain };
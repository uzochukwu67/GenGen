/**
 * check-registration.js — Check if chains are registered with GenLayer Oracle Hub
 */

const { createClient } = require('genlayer-js');
require('dotenv').config();

const GENLAYER_RPC = process.env.GENLAYER_RPC || 'https://studio.genlayer.com';
const HUB_ADDRESS = process.env.HUB_ADDRESS || '0x5286D78605d6D255A2FfF4911cC57ef35692e461';

async function checkRegistration() {
  console.log('🔍 Checking chain registrations...');

  const gl = createClient({ endpoint: GENLAYER_RPC, account: account });

  try {
    // Check if our specific chains are registered
    const chainsToCheck = ['polygon-amoy-v1', 'ethereum-mainnet', 'base-mainnet'];
    let registeredCount = 0;

    for (const chainKey of chainsToCheck) {
      const chainInfo = await gl.call(HUB_ADDRESS, 'get_chain', { chain_key: chainKey });
      console.log(`🔍 ${chainKey}:`, chainInfo ? '✅ Registered' : '❌ Not found');
      
      if (chainInfo) {
        registeredCount++;
        console.log(`   Adapter: ${chainInfo.adapter_address}`);
        console.log(`   Active: ${chainInfo.active ? '✅' : '❌'}`);
      }
    }

    console.log(`📋 ${registeredCount}/${chainsToCheck.length} chains registered`);

    if (registeredCount > 0) {
      console.log('✅ Some chains are registered!');
      return true;
    } else {
      console.log('❌ No chains are registered yet.');
      return false;
    }

  } catch (error) {
    console.error('❌ Check failed:', error.message);
    return false;
  }
}

if (require.main === module) {
  checkRegistration().catch(console.error);
}

module.exports = { checkRegistration };
// Test script to check genlayer-js import and basic connectivity
const { createClient } = require('genlayer-js');

console.log('✅ genlayer-js imported successfully');

const client = createClient({ endpoint: 'https://studio.genlayer.com' });
console.log('✅ GenLayer client created successfully');

const HUB_ADDRESS = '0x5286D78605d6D255A2FfF4911cC57ef35692e461';

async function testConnection() {
  try {
    console.log('🔍 Testing connection to GenLayer RPC...');
    const result = await client.call(HUB_ADDRESS, 'get_hub_stats', {});
    console.log('✅ Connection successful!');
    console.log('📊 Hub stats:', result);
  } catch (error) {
    console.error('❌ Connection failed:', error.message);
    console.error('Full error:', error);
  }
}

testConnection();
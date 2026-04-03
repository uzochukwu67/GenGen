#!/usr/bin/env python3

"""
validate_setup.py — Validate Oracle Consumer & Relayer Setup
===========================================================

Checks that all components are properly configured.

Usage:
  python validate_setup.py
"""

import os
import json
import sys
from pathlib import Path

def check_env_vars():
    """Check required environment variables."""
    print("🔍 Checking environment variables...")

    required_vars = [
        'ORACLE_HUB_CONTRACT_ADDRESS',
        'GENLAYER_RPC',
        'RELAYER_PRIVATE_KEY',
        'EVM_RPC_POLYGON',
        'CONSUMER_POLYGON'
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var) or os.getenv(var).startswith('your_') or os.getenv(var) == '0x0000000000000000000000000000000000000000':
            missing.append(var)

    if missing:
        print(f"⚠️  Missing or placeholder environment variables: {', '.join(missing)}")
        print("   Update your .env file with real values")
        return False

    print("✅ Environment variables configured")
    return True

def check_contract_files():
    """Check that contract files exist."""
    print("🔍 Checking contract files...")

    contracts_dir = Path(__file__).parent / 'contracts'
    required_files = [
        'OracleConsumer.sol',
        'oracle_hub.py',
        'relayer_keeper.py'
    ]

    missing = []
    for file in required_files:
        if not (contracts_dir / file).exists():
            missing.append(file)

    if missing:
        print(f"❌ Missing contract files: {', '.join(missing)}")
        return False

    print("✅ Contract files present")
    return True

def check_oracle_hub_deployment():
    """Check Oracle Hub deployment."""
    print("🔍 Checking Oracle Hub deployment...")

    hub_address = os.getenv('ORACLE_HUB_CONTRACT_ADDRESS')
    if not hub_address or hub_address == '0x5286D78605d6D255A2FfF4911cC57ef35692e461':
        print("❌ Oracle Hub not deployed or address not updated")
        return False

    print(f"✅ Oracle Hub deployed at: {hub_address}")
    return True

def check_dependencies():
    """Check Python dependencies."""
    print("🔍 Checking Python dependencies...")

    try:
        import genlayer
        print("✅ genlayer SDK available")
    except ImportError:
        print("❌ genlayer SDK not installed. Run: pip install genlayer")
        return False

    try:
        import web3
        print("✅ web3.py available")
    except ImportError:
        print("❌ web3.py not installed. Run: pip install web3")
        return False

    try:
        import dotenv
        print("✅ python-dotenv available")
    except ImportError:
        print("❌ python-dotenv not installed. Run: pip install python-dotenv")
        return False

    return True

def validate_oracle_consumer():
    """Validate OracleConsumer.sol syntax."""
    print("🔍 Validating OracleConsumer.sol...")

    contract_path = Path(__file__).parent / 'contracts' / 'OracleConsumer.sol'
    if not contract_path.exists():
        print("❌ OracleConsumer.sol not found")
        return False

    with open(contract_path, 'r') as f:
        content = f.read()

    # Basic syntax checks
    if 'pragma solidity' not in content:
        print("❌ Not a valid Solidity file")
        return False

    if 'contract OracleConsumer' not in content:
        print("❌ OracleConsumer contract not found")
        return False

    if 'function createMarket' not in content:
        print("❌ createMarket function missing")
        return False

    if 'function receiveVerdict' not in content:
        print("❌ receiveVerdict function missing")
        return False

    print("✅ OracleConsumer.sol structure valid")
    return True

def validate_relayer_keeper():
    """Validate relayer_keeper.py syntax."""
    print("🔍 Validating relayer_keeper.py...")

    try:
        import contracts.relayer_keeper as rk
        print("✅ relayer_keeper.py imports successfully")

        # Check if required classes exist
        if not hasattr(rk, 'OracleKeeper'):
            print("❌ OracleKeeper class missing")
            return False

        print("✅ relayer_keeper.py structure valid")
        return True

    except Exception as e:
        print(f"❌ relayer_keeper.py import failed: {e}")
        return False

def main():
    """Run all validations."""
    print("🚀 Validating Oracle Consumer & Relayer Setup\n")

    checks = [
        check_contract_files,
        check_env_vars,
        check_oracle_hub_deployment,
        check_dependencies,
        validate_oracle_consumer,
        validate_relayer_keeper,
    ]

    passed = 0
    total = len(checks)

    for check in checks:
        try:
            if check():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Check failed with error: {e}\n")

    print(f"📊 Results: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 Setup is complete! Ready to deploy Oracle Consumer and run Relayer.")
        print("\nNext steps:")
        print("1. Deploy OracleConsumer.sol to your target EVM chains")
        print("2. Update .env with deployed contract addresses")
        print("3. Register your chains with the Oracle Hub")
        print("4. Start the relayer keeper: python contracts/relayer_keeper.py")
        return True
    else:
        print("⚠️  Setup incomplete. Please address the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
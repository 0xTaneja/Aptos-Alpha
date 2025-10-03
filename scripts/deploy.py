#!/usr/bin/env python3
"""
Deployment script for Aptos Alpha Bot smart contracts
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / "python_bot"))

from aptos_client import AptosAlphaBotClient
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def deploy_contracts():
    """Deploy smart contracts to Aptos network"""
    try:
        logger.info("🚀 Starting contract deployment...")
        
        # Initialize client
        client = AptosAlphaBotClient(
            node_url=config.aptos.node_url,
            contract_address=config.aptos.contract_address,
            private_key=config.aptos.admin_private_key
        )
        
        logger.info(f"📡 Connected to: {config.aptos.node_url}")
        logger.info(f"🏠 Deploying to: {client.account.address()}")
        
        # Check balance
        balance = await client.get_account_balance()
        logger.info(f"💰 Account balance: {client.format_amount(balance)}")
        
        if balance < 100000000:  # 1 APT
            logger.warning("⚠️  Low balance for deployment. Consider funding account.")
        
        # Deploy contracts (in a real deployment, this would compile and publish Move modules)
        logger.info("📋 Deploying trading vault contract...")
        vault_result = await client.initialize_vault()
        if vault_result["status"] == "success":
            logger.info(f"✅ Vault deployed: {vault_result['txn_hash']}")
        else:
            logger.error(f"❌ Vault deployment failed: {vault_result['message']}")
            return False
        
        logger.info("📋 Deploying trading engine contract...")
        engine_result = await client.initialize_trading_engine()
        if engine_result["status"] == "success":
            logger.info(f"✅ Engine deployed: {engine_result['txn_hash']}")
        else:
            logger.error(f"❌ Engine deployment failed: {engine_result['message']}")
            return False
        
        logger.info("🎉 All contracts deployed successfully!")
        
        # Initialize market prices
        logger.info("📈 Initializing market prices...")
        prices = [
            ("APT/USDC", 1000000),    # $10.00
            ("BTC/USDC", 6500000000), # $65,000.00
            ("ETH/USDC", 300000000),  # $3,000.00
        ]
        
        for symbol, price in prices:
            result = await client.update_market_price(symbol, price)
            if result["status"] == "success":
                logger.info(f"✅ {symbol} price set: ${price/1000000:.2f}")
        
        logger.info("🎯 Deployment completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"💥 Deployment failed: {e}")
        return False

async def verify_deployment():
    """Verify that contracts are deployed correctly"""
    try:
        logger.info("🔍 Verifying deployment...")
        
        client = AptosAlphaBotClient(
            node_url=config.aptos.node_url,
            contract_address=config.aptos.contract_address,
            private_key=config.aptos.admin_private_key
        )
        
        # Test vault functions
        vault_stats = await client.get_vault_stats()
        logger.info(f"📊 Vault stats: {vault_stats}")
        
        # Test market prices
        apt_price = await client.get_market_price("APT/USDC")
        logger.info(f"💰 APT price: ${apt_price/1000000:.2f}")
        
        # Test user functions
        user_deposit = await client.get_user_deposit(str(client.account.address()))
        logger.info(f"👤 User deposit: {client.format_amount(user_deposit)}")
        
        logger.info("✅ Verification completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False

def print_deployment_info():
    """Print deployment information"""
    info = f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    DEPLOYMENT INFORMATION                    ║
    ╠══════════════════════════════════════════════════════════════╣
    ║ Network: {'Testnet' if config.aptos.testnet_mode else 'Mainnet':<49} ║
    ║ Node URL: {config.aptos.node_url:<47} ║
    ║ Contract: {config.aptos.contract_address:<47} ║
    ║                                                              ║
    ║ Features to Deploy:                                          ║
    ║ • Trading Vault (deposit, withdraw, profit sharing)         ║
    ║ • Trading Engine (orders, strategies, execution)            ║
    ║ • Grid Trading (automated strategies)                       ║
    ║ • Market Data (price feeds, analytics)                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(info)

async def main():
    """Main deployment function"""
    print_deployment_info()
    
    try:
        # Deploy contracts
        success = await deploy_contracts()
        if not success:
            logger.error("❌ Deployment failed")
            sys.exit(1)
        
        # Verify deployment
        success = await verify_deployment()
        if not success:
            logger.error("❌ Verification failed")
            sys.exit(1)
        
        logger.info("🎉 Deployment and verification completed successfully!")
        
        # Print next steps
        next_steps = """
        ╔══════════════════════════════════════════════════════════════╗
        ║                         NEXT STEPS                           ║
        ╠══════════════════════════════════════════════════════════════╣
        ║ 1. Set TELEGRAM_BOT_TOKEN in your environment               ║
        ║ 2. Run: python python_bot/main.py                           ║
        ║ 3. Test the bot with /start command                         ║
        ║ 4. Create demo trades and strategies                        ║
        ║ 5. Prepare hackathon demo                                   ║
        ╚══════════════════════════════════════════════════════════════╝
        """
        print(next_steps)
        
    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

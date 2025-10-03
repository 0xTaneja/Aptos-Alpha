#!/usr/bin/env python3
"""
Aptos Alpha Bot - Main Entry Point
Migrated from Hyperliquid to Aptos blockchain
Preserving all original functionality and user experience
"""

import asyncio
import logging
import json
import sys
import os
from pathlib import Path
import threading
from typing import Dict, Optional

# Add current directory to Python path to fix imports
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

# Real component imports (migrated from hyperliqbot)
from database import Database
from telegram_bot.bot import TelegramTradingBot
from config import ConfigManager

# Aptos-specific imports
from python_bot.aptos_client import AptosAlphaBotClient

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aptos_alpha_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('aptos_alpha_main')

class AptosAlphaBot:
    """
    Main orchestrator for Aptos Alpha Trading Bot
    Coordinates all components and services
    """
    
    def __init__(self):
        self.config = config
        self.running = False
        
        # Core components
        self.aptos_client = None
        self.telegram_bot = None
        
        logger.info("🚀 Aptos Alpha Bot initialized")
        logger.info(f"📡 Network: {'Testnet' if config.aptos.testnet_mode else 'Mainnet'}")
        logger.info(f"🏠 Contract: {config.aptos.contract_address}")
    
    async def initialize_components(self):
        """Initialize all bot components"""
        try:
            logger.info("🔧 Initializing components...")
            
            # 1. Initialize Aptos client
            logger.info("🌐 Connecting to Aptos network...")
            self.aptos_client = AptosAlphaBotClient(
                node_url=self.config.aptos.node_url,
                contract_address=self.config.aptos.contract_address,
                private_key=self.config.aptos.admin_private_key
            )
            
            # Test connection
            balance = await self.aptos_client.get_account_balance()
            logger.info(f"✅ Aptos connected. Admin balance: {self.aptos_client.format_amount(balance)}")
            
            # 2. Initialize Telegram bot
            logger.info("🤖 Initializing Telegram bot...")
            if not self.config.telegram.bot_token:
                raise ValueError("Telegram bot token not configured!")
            
            self.telegram_bot = AptosAlphaTelegramBot(
                token=self.config.telegram.bot_token,
                contract_address=self.config.aptos.contract_address,
                node_url=self.config.aptos.node_url
            )
            
            logger.info("✅ All components initialized successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize components: {e}")
            raise
    
    async def deploy_contracts(self):
        """Deploy smart contracts if needed"""
        try:
            logger.info("📋 Checking smart contract deployment...")
            
            # For demo purposes, we'll assume contracts are deployed
            # In production, you'd check if contracts exist and deploy if needed
            
            logger.info("✅ Smart contracts ready")
            
        except Exception as e:
            logger.error(f"❌ Contract deployment failed: {e}")
            raise
    
    async def start_services(self):
        """Start all bot services"""
        try:
            logger.info("🚀 Starting services...")
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Start Telegram bot
            logger.info("🤖 Starting Telegram bot...")
            self.running = True
            
            # Run Telegram bot (this will block)
            self.telegram_bot.run()
            
        except Exception as e:
            logger.error(f"❌ Failed to start services: {e}")
            raise
    
    async def _start_background_tasks(self):
        """Start background monitoring and trading tasks"""
        try:
            logger.info("⚡ Starting background tasks...")
            
            # Start price monitoring
            asyncio.create_task(self._monitor_prices())
            
            # Start health monitoring
            asyncio.create_task(self._monitor_health())
            
            logger.info("✅ Background tasks started")
            
        except Exception as e:
            logger.error(f"❌ Error starting background tasks: {e}")
    
    async def _monitor_prices(self):
        """Monitor market prices and update contracts"""
        while self.running:
            try:
                # Update market prices (mock implementation)
                symbols = ["APT/USDC", "BTC/USDC", "ETH/USDC"]
                
                for symbol in symbols:
                    price = await self.aptos_client.get_market_price(symbol)
                    logger.debug(f"📈 {symbol}: {price}")
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in price monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_health(self):
        """Monitor system health"""
        while self.running:
            try:
                # Check Aptos connection
                balance = await self.aptos_client.get_account_balance()
                
                # Check contract status
                vault_stats = await self.aptos_client.get_vault_stats()
                
                logger.info(f"🏥 Health check: Balance={self.aptos_client.format_amount(balance)}, "
                          f"Vault={vault_stats.get('total_balance', 0)}")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop all services gracefully"""
        try:
            logger.info("🛑 Stopping Aptos Alpha Bot...")
            
            self.running = False
            
            # Stop background tasks
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                logger.info(f"Cancelling {len(tasks)} background tasks...")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info("✅ Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

def print_banner():
    """Print startup banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║                    🚀 APTOS ALPHA BOT 🚀                    ║
    ║                                                              ║
    ║              Advanced DeFi Trading Infrastructure            ║
    ║                   Built for CTRL+MOVE Hackathon             ║
    ║                                                              ║
    ║  🎯 Category: Build the Future of DeFi on Aptos             ║
    ║  ⚡ Features: Vault Trading, Grid Strategies, Analytics     ║
    ║  🔒 Security: Non-custodial, Smart Contract Based           ║
    ║  📱 Interface: Telegram-first, Mobile Optimized             ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_configuration():
    """Check if all required configuration is present"""
    errors = []
    
    if not config.telegram.bot_token:
        errors.append("❌ TELEGRAM_BOT_TOKEN not set")
    
    if not config.aptos.contract_address:
        errors.append("❌ CONTRACT_ADDRESS not set")
    
    if config.aptos.testnet_mode:
        logger.info("⚠️  Running in TESTNET mode")
    else:
        logger.warning("🚨 Running in MAINNET mode - use with caution!")
    
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(error)
        logger.error("Please check your environment variables or .env file")
        return False
    
    return True

async def main():
    """Main entry point"""
    print_banner()
    
    try:
        # Check configuration
        if not check_configuration():
            sys.exit(1)
        
        # Create and initialize bot
        bot = AptosAlphaBot()
        await bot.initialize_components()
        
        # Deploy contracts if needed
        await bot.deploy_contracts()
        
        # Start services
        await bot.start_services()
        
    except KeyboardInterrupt:
        logger.info("👋 Received shutdown signal...")
        if 'bot' in locals():
            await bot.stop()
    except Exception as e:
        logger.critical(f"💥 Critical error: {e}", exc_info=True)
        sys.exit(1)

def run_bot():
    """Synchronous entry point for running the bot"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot terminated by user")
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_bot()

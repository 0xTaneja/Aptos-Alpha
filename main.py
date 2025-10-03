#!/usr/bin/env python3
"""
Aptos Alpha Trading Bot - Main Entry Point
Native Aptos blockchain trading bot with full DeFi integration
Production-ready for CTRL+MOVE Hackathon
"""

import asyncio
import logging
import json
import sys
import os
from pathlib import Path
# import threading  # Not needed - using async/await
from typing import Dict, Optional

# Add current directory to Python path to fix imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Aptos Alpha Bot component imports
from database import DatabaseManager as Database
from telegram_bot.aptos_bot import TelegramTradingBot
from config import ConfigManager

# Aptos SDK and client imports
try:
    from aptos_sdk.async_client import RestClient
    from aptos_sdk.account import Account as AptosAccount
    APTOS_SDK_AVAILABLE = True
except ImportError:
    APTOS_SDK_AVAILABLE = False
    logger.warning("Aptos SDK not available, using fallback client")

# Import our new Aptos components
from aptos.exchange import AptosExchange
from aptos.info import AptosInfo
from aptos_auth import AptosAuth
from aptos_utils import setup, quick_setup
# from python_bot.aptos_client import AptosAlphaBotClient  # Removed - using RestClient directly

# Import sponsor integrations
from integrations import MerklePerpetuals, KanaFutures

# Import real trading components
from trading_engine.vault_manager import VaultManager
from strategies.grid_trading_engine import GridTradingEngine
from trading_engine.trading_analytics import AptosAnalytics
from telegram_bot.perpetuals_commands import PerpetualsCommands

# Import ALL strategies for complete functionality
from strategies.automated_trading import AutomatedTrading, RealAutomatedTradingEngine
from strategies.premium import RealPremiumCommands
from strategies.simple_trader import SimpleTrader
from strategies.strategy_manager import AptosStrategyManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aptos_alpha_bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configure StreamHandler to use UTF-8
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

logger = logging.getLogger(__name__)

class AptosAlphaBot:
    """
    Main orchestrator for the Aptos Alpha Trading Bot
    Native Aptos blockchain integration with full DeFi capabilities
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config  # Use .config attribute
        self.running = False
        
        # Core Aptos components
        self.database = None
        self.aptos_client = None
        self.telegram_bot = None
        self.rest_client = None
        self.aptos_auth = None
        self.aptos_exchange = None
        self.aptos_info = None
        
        # Sponsor integrations - Perpetuals
        self.merkle_perps = None
        self.kana_futures = None
        self.perp_commands = None
        
        # Aptos trading configuration
        self.trading_enabled = False  # Master switch for all trading activities
        self.node_url = self.config.get("general", {}).get("node_url", "https://fullnode.testnet.aptoslabs.com/v1")
        self.network = self.config.get("general", {}).get("environment", "testnet")
        
        logger.info("AptosAlphaBot initialized with trading DISABLED")
    
    async def initialize_components(self):
        """Initialize all components in proper dependency order with enhanced error handling"""
        try:
            logger.info("🔧 Initializing AptosAlphaBot components...")
            
            # 1. Initialize Aptos Database
            logger.info("📚 Initializing Aptos database...")
            try:
                self.database = Database()
                await self.database.initialize()
                # Test database connection
                await self.database.execute("SELECT 1")
                logger.info("✅ Aptos database initialized and tested")
            except Exception as e:
                logger.error(f"Aptos database initialization failed: {e}")
                # Create fallback database
                self.database = self._create_fallback_database()
                logger.warning("⚠️ Using fallback database implementation")
            
            # 2. Initialize Aptos Authentication and Core Components
            logger.info("🌐 Initializing Aptos authentication and clients...")
            try:
                # Initialize Aptos authentication
                self.aptos_auth = AptosAuth(
                    config_dir=".",
                    network=self.network,
                    auto_reconnect=True
                )
                
                # Connect and get components
                address, info, exchange = await self.aptos_auth.connect()
                self.aptos_info = info
                self.aptos_exchange = exchange
                
                logger.info(f"✅ Aptos authentication successful: {address}")
                
                # Initialize REST client for direct API access
                if APTOS_SDK_AVAILABLE:
                    self.rest_client = RestClient(self.node_url)
                    logger.info(f"✅ Aptos REST client initialized: {self.node_url}")
                
                # Store REST client directly
                self.aptos_client = self.rest_client
                
                # Test connection with balance check
                balance = await self.aptos_info.get_account_balance(address)
                logger.info(f"✅ Account balance: {balance / 100000000:.8f} APT")
                
                # Load bot config for sponsor integrations
                try:
                    with open('bot_config.json', 'r') as f:
                        bot_config = json.load(f)
                    
                    # Reinitialize exchange with config for Panora integration
                    account = self.aptos_auth.account
                    self.aptos_exchange = AptosExchange(
                        account=account,
                        node_url=self.node_url,
                        config=bot_config  # Pass config to enable Panora
                    )
                    logger.info("✅ Aptos Exchange reinitialized with sponsor integrations (Panora enabled)")
                except Exception as config_error:
                    logger.warning(f"Could not reload config for integrations: {config_error}")
                
                # Initialize sponsor integrations - Perpetuals
                logger.info("🚀 Initializing sponsor perpetuals integrations...")
                try:
                    self.merkle_perps = MerklePerpetuals(
                        aptos_client=self.rest_client,
                        account=self.aptos_auth.account
                    )
                    logger.info("✅ Merkle Trade perpetuals initialized (up to 100x leverage)")
                    
                    self.kana_futures = KanaFutures(
                        aptos_account=self.aptos_auth.account
                    )
                    logger.info("✅ Kana Labs futures initialized (up to 50x leverage)")
                    
                except Exception as perp_error:
                    logger.error(f"Perpetuals initialization failed: {perp_error}")
                    logger.warning("⚠️ Continuing without perpetuals trading")
                
            except Exception as e:
                logger.error(f"❌ Aptos authentication failed: {e}")
                raise RuntimeError(f"Failed to initialize Aptos connection: {e}")
            
            # 3. Initialize Telegram bot (same structure as original)
            logger.info("🤖 Initializing Telegram bot...")
            try:
                telegram_config = self.config.get("telegram_bot", {})
                bot_token = telegram_config.get("bot_token", "")
                
                if not bot_token:
                    raise ValueError("Telegram bot token not configured!")
                
                # Initialize perpetuals commands if integrations loaded
                if self.merkle_perps and self.kana_futures:
                    try:
                        self.perp_commands = PerpetualsCommands(
                            merkle_perps=self.merkle_perps,
                            kana_futures=self.kana_futures,
                            database=self.database
                        )
                        logger.info("✅ Perpetuals commands initialized")
                    except Exception as perp_cmd_error:
                        logger.error(f"Perpetuals commands init failed: {perp_cmd_error}")
                        self.perp_commands = None
                
                # Initialize real trading components
                try:
                    contract_address = self.config.get("aptos", {}).get("contract_address")
                    
                    # Vault Manager for deposits/withdrawals
                    self.vault_manager = VaultManager(
                        vault_address=contract_address,
                        node_url=self.node_url,
                        client=self.rest_client,
                        vault_account=self.aptos_auth.account if self.aptos_auth else None
                    )
                    await self.vault_manager.initialize()
                    logger.info("✅ VaultManager initialized")
                    
                    # Grid Trading Engine
                    self.grid_engine = GridTradingEngine(
                        client=self.rest_client,
                        account=self.aptos_auth.account if self.aptos_auth else None,
                        contract_address=contract_address
                    )
                    logger.info("✅ GridTradingEngine initialized")
                    
                    # Trading Analytics (static class - just pass reference)
                    self.trading_analytics = AptosAnalytics
                    logger.info("✅ TradingAnalytics initialized")
                    
                    # Strategy Manager to coordinate all strategies
                    self.strategy_manager = AptosStrategyManager(
                        client=self.rest_client,
                        account=self.aptos_auth.account if self.aptos_auth else None,
                        config=self.config
                    )
                    logger.info("✅ AptosStrategyManager initialized")
                    
                    # Initialize individual strategies
                    self.automated_strategy = RealAutomatedTradingEngine(
                        client=self.rest_client,
                        account=self.aptos_auth.account if self.aptos_auth else None
                    )
                    self.premium_strategy = RealPremiumCommands(
                        client=self.rest_client,
                        account=self.aptos_auth.account if self.aptos_auth else None
                    )
                    self.simple_trader = SimpleTrader(
                        client=self.rest_client,
                        account=self.aptos_auth.account if self.aptos_auth else None
                    )
                    logger.info("✅ All trading strategies initialized (Automated, Premium, Simple)")
                    
                except Exception as engine_error:
                    logger.error(f"Trading engines init failed: {engine_error}", exc_info=True)
                    self.vault_manager = None
                    self.grid_engine = None
                    self.trading_analytics = None
                    self.strategy_manager = None
                    self.automated_strategy = None
                    self.premium_strategy = None
                    self.simple_trader = None
                
                # Initialize TelegramTradingBot with full Aptos integration
                self.telegram_bot = TelegramTradingBot(
                    token=bot_token,
                    config=self.config,
                    database=self.database,
                    aptos_client=self.aptos_client,      # Legacy client for compatibility
                    aptos_exchange=self.aptos_exchange,  # New exchange component
                    aptos_info=self.aptos_info,          # New info component
                    aptos_auth=self.aptos_auth,          # Authentication component
                    rest_client=self.rest_client,        # REST client for direct API access
                    perp_commands=self.perp_commands,    # Perpetuals trading commands
                    vault_manager=self.vault_manager,    # Vault management
                    grid_engine=self.grid_engine,        # Grid trading
                    trading_analytics=self.trading_analytics,  # Analytics
                    strategy_manager=self.strategy_manager,    # Strategy coordination
                    automated_strategy=self.automated_strategy,  # Automated trading
                    premium_strategy=self.premium_strategy,      # Premium features
                    simple_trader=self.simple_trader            # Simple trading
                )
                
                logger.info("✅ Telegram bot initialized with all dependencies")
                
                # Log sponsor integration status
                sponsors_enabled = []
                if self.aptos_exchange and hasattr(self.aptos_exchange, 'panora_enabled') and self.aptos_exchange.panora_enabled:
                    sponsors_enabled.append("Panora DEX Aggregator")
                if self.merkle_perps:
                    sponsors_enabled.append("Merkle Trade Perpetuals")
                if self.kana_futures:
                    sponsors_enabled.append("Kana Labs Futures")
                
                if sponsors_enabled:
                    logger.info(f"🎯 SPONSOR INTEGRATIONS ACTIVE: {', '.join(sponsors_enabled)}")
                else:
                    logger.warning("⚠️ No sponsor integrations active")
                
            except Exception as e:
                logger.error(f"❌ Telegram bot initialization failed: {e}", exc_info=True)
                raise RuntimeError(f"Failed to initialize Telegram bot: {e}")
            
            # Final health check
            await self._perform_health_check()
            logger.info("🚀 All components initialized successfully!")
            
        except Exception as e:
            logger.critical(f"Failed to initialize components: {e}")
            raise
    
    def _create_fallback_database(self):
        """Create fallback database for demo mode"""
        class FallbackDatabase:
            async def initialize(self): pass
            async def execute(self, query): return []
            async def get_user_stats(self, user_id): return {}
            async def record_trade(self, user_id, trade_data): pass
            async def close(self): pass
        
        return FallbackDatabase()
    
    async def _perform_health_check(self):
        """Perform comprehensive health check of all components"""
        health_status = {
            'aptos_client': False,
            'rest_client': False,
            'database': False,
            'telegram_bot': False,
        }
        
        # Check Aptos bot client
        try:
            if self.aptos_client:
                balance = await self.aptos_info.get_account_balance(str(self.aptos_auth.address))
                health_status['aptos_client'] = balance >= 0
        except Exception:
            pass
        
        # Check Aptos REST client
        try:
            if self.rest_client:
                ledger_info = await self.rest_client.get_ledger_information()
                health_status['rest_client'] = bool(ledger_info)
        except Exception:
            pass
        
        # Check database
        try:
            await self.database.execute("SELECT 1")
            health_status['database'] = True
        except Exception:
            pass
        
        # Check Telegram bot
        health_status['telegram_bot'] = self.telegram_bot is not None
        
        # Log health status
        healthy_components = sum(1 for v in health_status.values() if v)
        total_components = len(health_status)
        
        logger.info(f"🏥 Health check: {healthy_components}/{total_components} components healthy")
        
        # Include more detailed output about which components failed
        failed_components = [k for k, v in health_status.items() if not v]
        
        if failed_components:
            logger.warning(f"⚠️ Unhealthy components: {', '.join(failed_components)}")
        
        if healthy_components < total_components * 0.7:  # Less than 70% healthy
            logger.warning("⚠️ System health below optimal - some features may be limited")
        
        return health_status

    async def start_background_tasks(self):
        """Start background monitoring tasks"""
        try:
            logger.info("⚡ Initializing background tasks...")
            
            # Initialize basic system health monitoring
            if self.aptos_client:
                await self._start_basic_monitoring()
                logger.info("📊 Basic system monitoring enabled")
            
            logger.info("✅ System monitoring initialized, ALL TRADING DISABLED")
            logger.info("🤖 Trading is DISABLED - use Telegram commands to start trading when ready")
            
        except Exception as e:
            logger.error(f"Error initializing background tasks: {e}")
    
    async def _start_basic_monitoring(self):
        """Start only the basic system monitoring (no trading)"""
        asyncio.create_task(self._monitor_system_health())
        logger.info("🏥 Basic system health monitoring started")
    
    async def _monitor_system_health(self):
        """Monitor only basic system health - no trading activities"""
        while self.running:
            try:
                # Simple connection check
                if self.aptos_client:
                    try:
                        balance = await self.aptos_info.get_account_balance(str(self.aptos_auth.address))
                        logger.info(f"System health: Aptos connection OK, balance: {balance / 100000000:.8f} APT")
                    except Exception as e:
                        logger.warning(f"Aptos connection check failed: {e}")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in system health monitoring: {e}")
                await asyncio.sleep(60)
    
    async def toggle_auto_trading(self, enabled: bool) -> Dict:
        """Enable or disable auto-trading globally"""
        previous_state = self.trading_enabled
        self.trading_enabled = enabled
        
        if enabled and not previous_state:
            logger.info("🚀 Trading ENABLED - but individual components need manual activation")
            return {
                "status": "success", 
                "message": "Trading enabled, but individual components need manual activation. Use specific commands to start each component."
            }
            
        elif not enabled and previous_state:
            logger.info("🛑 Trading DISABLED - all trading operations will be blocked")
            return {"status": "success", "message": "Trading disabled, all trading operations blocked"}
        else:
            state_str = "enabled" if enabled else "disabled"
            return {"status": "info", "message": f"Trading already {state_str}"}
    
    async def start(self):
        """Start the unified bot system"""
        try:
            logger.info("🚀 Starting Aptos Alpha Trading Bot (TRADING DISABLED)...")
            
            # Initialize all components
            await self.initialize_components()
            
            # Start background tasks (only monitoring, no trading)
            self.running = True
            await self.start_background_tasks()
            
            # Start Telegram bot polling
            if self.telegram_bot:
                logger.info("🤖 Starting Telegram bot polling...")
                # Start bot asynchronously
                await self.telegram_bot.app.initialize()
                await self.telegram_bot.app.start()
                await self.telegram_bot.app.updater.start_polling()
                logger.info("🤖 Telegram bot started and polling")
            else:
                logger.warning("Telegram bot not initialized, cannot start polling.")
            
            logger.info("✅ Aptos Alpha Bot main components started. Telegram bot polling in background.")
            # Keep the main bot alive
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Failed to start bot: {e}", exc_info=True)
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the bot gracefully"""
        try:
            logger.info("🛑 Stopping Aptos Alpha Trading Bot...")
            
            self.running = False
            
            # Stop Telegram bot polling if it's running
            if self.telegram_bot and hasattr(self.telegram_bot, 'app') and hasattr(self.telegram_bot.app, 'running'):
                logger.info("Stopping Telegram bot polling...")
                await self.telegram_bot.app.stop()

            # Cancel background tasks
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                logger.info(f"Cancelling {len(tasks)} background tasks...")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info("Background tasks cancelled.")

            # Close database connection
            if self.database and hasattr(self.database, 'close') and asyncio.iscoroutinefunction(self.database.close):
                await self.database.close()
            
            logger.info("✅ Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}", exc_info=True)

def create_default_config():
    """Create default Aptos configuration file for the bot"""
    default_config = {
        "general": {
            "environment": "testnet",
            "node_url": "https://fullnode.testnet.aptoslabs.com/v1",
            "faucet_url": "https://faucet.testnet.aptoslabs.com",
            "log_level": "INFO"
        },
        "aptos": {
            "contract_address": "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69",
            "admin_private_key": "",
            "testnet_mode": True,
            "gas_unit_price": 100,
            "max_gas_amount": 10000
        },
        "telegram_bot": {
            "bot_token": "GET_TOKEN_FROM_BOTFATHER",
            "bot_username": "AptosAlphaBot",
            "allowed_users": [],
            "admin_users": [],
            "welcome_message": "Welcome to Aptos Alpha Trading Bot! Use /start to begin."
        },
        "trading": {
            "minimum_deposit_apt": 1.0,      # 1 APT
            "performance_fee_bps": 1000,     # 10%
            "lockup_period": 86400,          # 1 day
            "default_grid_spacing": 50,      # 0.5%
            "default_grid_levels": 10,
            "default_amount_per_level_apt": 0.1,  # 0.1 APT
            "dex_contracts": {
                "pancakeswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",
                "thala": "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af"
            }
        },
        "risk_management": {
            "max_daily_loss_percentage": 5.0,
            "max_position_size_apt": 10.0,
            "enable_emergency_stop": True
        }
    }
    
    with open("config.json", "w") as f:
        json.dump(default_config, f, indent=2)
    
    logger.info("✅ Created default config.json")
    return default_config

async def main():
    """Main entry point with comprehensive error handling"""
    bot_instance = None
    try:
        # Check for config file
        config_path = Path("config.json")
        if not config_path.exists():
            logger.info("📝 Config file not found. Creating default configuration...")
            create_default_config()
            logger.info(f"ℹ️ Please review and update '{config_path}' with your settings.")

        # Create and start the bot
        bot_instance = AptosAlphaBot()
        await bot_instance.start()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
        if bot_instance:
            await bot_instance.stop()
    except Exception as e:
        logger.critical(f"💥 Unhandled critical error in main: {e}", exc_info=True)
        if bot_instance:
            await bot_instance.stop()
        raise
    finally:
        if bot_instance and bot_instance.running:
            logger.info("Initiating graceful shutdown from finally block...")
            await bot_instance.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Main process terminated by KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"💥 Fatal error in main execution: {e}", exc_info=True)
        sys.exit(1)

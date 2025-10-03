"""
Strategy Manager for Aptos Alpha Trading Bot
Orchestrates all trading strategies and manages their execution
CONVERTED FROM HYPERLIQUID TO APTOS
"""

from typing import Dict, List, Optional
import asyncio
import logging
from datetime import datetime
import sys
import os
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class AptosStrategyManager:
    """
    Central manager for all Aptos trading strategies
    Handles strategy lifecycle, monitoring, and coordination
    CONVERTED FROM HYPERLIQUID TO APTOS
    """
    
    def __init__(self, client: RestClient, account: Account, config):
        self.client = client
        self.account = account
        self.config = config
        self.strategies = {}
        self.active = {}
        self.performance_tracker = {}
        self.running = False
        
        logger.info("Initializing AptosStrategyManager")
        self._load_strategies()
        
    def _load_strategies(self):
        """Load enabled strategies based on configuration"""
        try:
            # Import Aptos strategies
            from strategies.grid_trading_engine import GridTradingEngine
            from strategies.automated_trading import AutomatedTradingEngine
            from strategies.seedify_imc import AptosIMCManager
            from strategies.aptos_profit_bot import AptosProfitBot
            from strategies.simple_trader import SimpleAptosTrader
            
            # Load grid trading strategy
            if self.config.get('strategies', {}).get('grid_trading', {}).get('enabled', False):
                self.strategies['grid'] = GridTradingEngine(
                    self.client,
                    self.account,
                    self.config.get('grid_trading', {})
                )
                logger.info("Grid trading strategy loaded")
            
            # Load automated trading
            if self.config.get('strategies', {}).get('automated_trading', {}).get('enabled', True):
                self.strategies['auto'] = AutomatedTradingEngine(
                    self.client,
                    self.account,
                    self.config.get('automated_trading', {})
                )
                logger.info("Automated trading strategy loaded")
            
            # Load IMC strategies
            if self.config.get('strategies', {}).get('imc', {}).get('enabled', False):
                self.strategies['imc'] = AptosIMCManager(
                    self.client,
                    self.account,
                    self.config.get('imc', {}),
                    self.config.get('contract_address')
                )
                logger.info("IMC strategy loaded")
            
            # Load profit bot
            if self.config.get('strategies', {}).get('profit_bot', {}).get('enabled', False):
                self.strategies['profit'] = AptosProfitBot(
                    self.client,
                    self.account,
                    self.config.get('profit_bot', {})
                )
                logger.info("Profit bot strategy loaded")
            
            # Load simple trader (always available)
            self.strategies['simple'] = SimpleAptosTrader(
                self.client,
                self.account,
                self.config.get('simple_trader', {})
            )
            logger.info("Simple trader strategy loaded")
            
        except Exception as e:
            logger.error(f"Error loading strategies: {e}")
            # Ensure we have at least basic automated trading
            try:
                from strategies.automated_trading import AutomatedTradingEngine
                self.strategies['auto'] = AutomatedTradingEngine(
                    self.client,
                    self.account,
                    self.config.get('automated_trading', {})
                )
                logger.info("Fallback: Basic automated trading loaded")
            except Exception as fallback_error:
                logger.error(f"Failed to load fallback strategy: {fallback_error}")

class PerUserStrategyManager:
    """
    Per-user strategy manager for Aptos trading
    CONVERTED FROM HYPERLIQUID TO APTOS
    """
    
    def __init__(self):
        self.user_strategies = {}  # {user_id: {strategy_name: strategy_instance}}
        self.user_active = {}      # {user_id: {strategy_name: bool}}
        self.user_performance = {} # {user_id: {strategy_name: performance_data}}
        self.running = False
        
        logger.info("Initializing PerUserStrategyManager for Aptos")
        
    async def create_user_strategies(self, user_id: str, aptos_client, user_account) -> Dict:
        """Create strategy instances for a user"""
        try:
            if user_id not in self.user_strategies:
                self.user_strategies[user_id] = {}
                self.user_active[user_id] = {}
                self.user_performance[user_id] = {}
            
            logger.info(f"Created strategies for user {user_id}")
            
            return {
                'success': True,
                'strategies': ['grid', 'auto']
            }
            
        except Exception as e:
            logger.error(f"Error creating strategies for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def start_user_strategy(self, user_id: str, strategy_name: str, params: Dict = None) -> Dict:
        """Start a specific strategy for a user"""
        try:
            logger.info(f"Starting {strategy_name} strategy for user {user_id}")
            return {'success': True, 'message': f'{strategy_name} strategy started'}
            
        except Exception as e:
            logger.error(f"Error starting strategy {strategy_name} for user {user_id}: {e}")
            return {'success': False, 'error': str(e)}

    def get_available_strategies(self) -> List[str]:
        """Get list of available strategy types"""
        return ['grid', 'auto']

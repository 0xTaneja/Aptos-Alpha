import asyncio
from asyncio.log import logger
import time
from typing import Dict, Optional, TYPE_CHECKING
import os
import sys
import logging

# Aptos SDK imports (replacing Hyperliquid)
from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

# Import the agent factory for user wallet management (to be converted)
from trading_engine.agent_factory import AgentFactory

# Import strategy manager (to be converted)
from strategies.strategy_manager import PerUserStrategyManager

# Add MultiUserTradingEngine implementation converted to Aptos
class MultiUserTradingEngine:
    """
    Multi-user trading engine that maintains isolated user environments
    Each user has their own Aptos account and strategies
    """
    def __init__(self, master_private_key: str, base_url: str = None):
        """
        Initialize the multi-user trading engine for Aptos
        
        Args:
            master_private_key: Private key for the master wallet used to create agent wallets
            base_url: Aptos node URL (defaults to testnet)
        """
        self.base_url = base_url or "https://fullnode.testnet.aptoslabs.com/v1"
        self.contract_address = "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        
        # Initialize Aptos client
        self.client = RestClient(self.base_url)
        
        # Master account for creating agent wallets
        if master_private_key:
            self.master_account = Account.load_key(master_private_key)
        else:
            self.master_account = Account.generate()
        
        # Agent factory for creating user wallets (to be converted)
        self.agent_factory = AgentFactory(master_private_key, base_url=self.base_url)
        
        # User management (same structure as original)
        self.user_strategies = {}  # {user_id: {strategy_name: strategy_instance}}
        self.user_accounts = {}    # {user_id: Account} - Aptos accounts instead of Exchange
        self.user_tasks = {}       # {user_id: {strategy_name: asyncio.Task}}
        self.strategy_manager = PerUserStrategyManager()
        
        # Cache for market data (same as original)
        self.mids_cache = {}
        self.mids_cache_time = 0
        self.mids_cache_ttl = 5  # 5 seconds TTL
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("MultiUserTradingEngine initialized for Aptos")
        
        # Set the singleton instance
        MultiUserTradingEngine._instance = self

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, '_instance') or cls._instance is None:
            return None
        return cls._instance

    async def initialize(self) -> bool:
        """Initialize the trading engine and its components"""
        try:
            # Initialize agent factory (to be converted)
            await self.agent_factory.initialize()
            
            # Test connection to Aptos API
            if await self.validate_connection():
                self.logger.info("Connection to Aptos API validated")
                return True
            else:
                self.logger.error("Failed to validate connection to Aptos API")
                return False
        except Exception as e:
            self.logger.error(f"Error initializing MultiUserTradingEngine: {e}")
            return False

    async def validate_connection(self) -> bool:
        """Validate connection to Aptos network"""
        try:
            # Test by getting account balance
            from aptos_sdk.account_address import AccountAddress
            address_obj = AccountAddress.from_str(str(self.master_account.address()))
            balance = await self.client.account_balance(address_obj)
            self.logger.info(f"Master account balance: {balance}")
            return True
        except Exception as e:
            self.logger.error(f"Connection validation failed: {e}")
            return False

    async def get_all_mids(self) -> Dict[str, float]:
        """
        Get market data for Aptos trading pairs
        Uses caching to reduce API calls
        
        Returns:
            Dict mapping coin symbols to their current prices
        """
        current_time = time.time()
        
        # Return cached values if still valid
        if self.mids_cache and current_time - self.mids_cache_time < self.mids_cache_ttl:
            return self.mids_cache
        
        try:
            # Get market prices from Aptos smart contract
            # This would call a view function on our trading_engine contract
            market_prices = await self._get_market_prices_from_contract()
            
            self.mids_cache = market_prices
            self.mids_cache_time = current_time
            
            return market_prices
            
        except Exception as e:
            self.logger.error(f"Error fetching market data: {e}")
            # Return cached data if available, otherwise empty dict
            return self.mids_cache if self.mids_cache else {}

    async def _get_market_prices_from_contract(self) -> Dict[str, float]:
        """Get market prices from Aptos DEX contracts and external APIs"""
        try:
            prices = {}
            
            # Get APT price from CoinGecko
            try:
                import requests
                response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=aptos&vs_currencies=usd", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    prices["APT"] = data.get("aptos", {}).get("usd", 10.0)
                else:
                    prices["APT"] = 10.0
            except:
                prices["APT"] = 10.0
            
            # Query DEX contracts for other token prices
            dex_contracts = [
                "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",  # PancakeSwap
                "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af",  # Thala
            ]
            
            for contract in dex_contracts:
                try:
                    resources = await self.client.account_resources(contract)
                    for resource in resources:
                        if "TokenPairReserve" in resource["type"]:
                            data = resource["data"]
                            reserve_x = int(data.get("reserve_x", 0))
                            reserve_y = int(data.get("reserve_y", 0))
                            
                            if reserve_x > 0 and reserve_y > 0:
                                # Calculate price ratio
                                price_ratio = reserve_y / reserve_x
                                
                                # Extract token symbols from type
                                type_args = resource["type"].split("<")[1].split(">")[0].split(",")
                                if len(type_args) >= 2:
                                    token_x = type_args[0].strip().split("::")[-1]
                                    token_y = type_args[1].strip().split("::")[-1]
                                    
                                    if token_x not in prices:
                                        prices[token_x] = price_ratio * prices.get("APT", 10.0)
                                    if token_y not in prices:
                                        prices[token_y] = (1 / price_ratio) * prices.get("APT", 10.0)
                                        
                except Exception as e:
                    self.logger.debug(f"Error querying DEX contract {contract}: {e}")
                    continue
            
            # Add stablecoin prices
            prices.update({
                "USDC": 1.0,
                "USDT": 1.0,
                "DAI": 1.0
            })
            
            return prices
            
        except Exception as e:
            self.logger.error(f"Error getting market prices: {e}")
            return {"APT": 10.0, "USDC": 1.0}

    async def create_user_trader(self, user_id: str, agent_private_key: str, main_address: str) -> Dict:
        """
        Create a new user trader with Aptos account
        
        Args:
            user_id: Unique identifier for the user
            agent_private_key: Private key for the user's agent wallet
            main_address: User's main Aptos address
            
        Returns:
            Dict with status and account info
        """
        try:
            # Create Aptos account from private key
            user_account = Account.load_key(agent_private_key)
            
            # Store user account
            self.user_accounts[user_id] = user_account
            
            # Initialize user strategies dict
            self.user_strategies[user_id] = {}
            self.user_tasks[user_id] = {}
            
            self.logger.info(f"Created user trader for {user_id} with address {user_account.address()}")
            
            return {
                "status": "success",
                "user_id": user_id,
                "address": str(user_account.address()),
                "main_address": main_address
            }
            
        except Exception as e:
            self.logger.error(f"Error creating user trader for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def place_order(self, user_id: str, symbol: str, side: str, amount: float, price: float, order_type: str = "limit") -> Dict:
        """
        Place an order for a user using Aptos smart contract
        
        Args:
            user_id: User identifier
            symbol: Trading pair (e.g., "APT/USDC")
            side: "buy" or "sell"
            amount: Order amount
            price: Order price
            order_type: Order type (default "limit")
            
        Returns:
            Dict with order result
        """
        try:
            if user_id not in self.user_accounts:
                return {"status": "error", "message": "User not found"}
            
            user_account = self.user_accounts[user_id]
            
            # Convert amounts to proper units (APT uses 8 decimals)
            amount_units = int(amount * 100000000)  # Convert to octas
            price_units = int(price * 1000000)     # Convert to micro-dollars
            
            # Prepare transaction to call place_order on smart contract
            side_value = 1 if side.lower() == "buy" else 2
            
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "place_order",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(symbol.encode(), Serializer.to_bytes),
                    TransactionArgument(side_value, Serializer.u8),
                    TransactionArgument(amount_units, Serializer.u64),
                    TransactionArgument(price_units, Serializer.u64),
                ]
            )
            
            # Submit transaction
            txn_hash = await self._submit_transaction(user_account, payload)
            
            self.logger.info(f"Order placed for {user_id}: {side} {amount} {symbol} @ {price}")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "order_type": order_type
            }
            
        except Exception as e:
            self.logger.error(f"Error placing order for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def cancel_order(self, user_id: str, order_id: int) -> Dict:
        """
        Cancel an order for a user
        """
        try:
            if user_id not in self.user_accounts:
                return {"status": "error", "message": "User not found"}
            
            user_account = self.user_accounts[user_id]
            
            # Prepare transaction to call cancel_order on smart contract
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "cancel_order",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(order_id, Serializer.u64),
                ]
            )
            
            # Submit transaction
            txn_hash = await self._submit_transaction(user_account, payload)
            
            self.logger.info(f"Order {order_id} cancelled for {user_id}")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "order_id": order_id
            }
            
        except Exception as e:
            self.logger.error(f"Error cancelling order for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_user_orders(self, user_id: str) -> Dict:
        """
        Get user's orders from Aptos smart contract
        """
        try:
            if user_id not in self.user_accounts:
                return {"status": "error", "message": "User not found"}
            
            user_account = self.user_accounts[user_id]
            address = str(user_account.address())
            
            # Query user orders from trading contract
            try:
                resources = await self.client.account_resources(address)
                orders = []
                
                for resource in resources:
                    if "UserOrders" in resource["type"]:
                        orders_data = resource["data"]
                        orders = orders_data.get("orders", [])
                        break
                
                return {
                    "status": "success",
                    "orders": orders,
                    "count": len(orders)
                }
                
            except Exception as e:
                self.logger.error(f"Error querying user orders: {e}")
                return {
                    "status": "success",
                    "orders": [],
                    "count": 0
                }
            
        except Exception as e:
            self.logger.error(f"Error getting orders for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_user_balance(self, user_id: str) -> Dict:
        """
        Get user's balance from Aptos account
        """
        try:
            if user_id not in self.user_accounts:
                return {"status": "error", "message": "User not found"}
            
            user_account = self.user_accounts[user_id]
            address = str(user_account.address())
            
            # Get APT balance
            from aptos_sdk.account_address import AccountAddress
            address_obj = AccountAddress.from_str(address)
            apt_balance = await self.client.account_balance(address_obj)
            
            # Get vault deposits from trading contract
            vault_deposit = 0
            try:
                resources = await self.client.account_resources(address)
                for resource in resources:
                    if "UserDeposit" in resource["type"]:
                        deposit_data = resource["data"]
                        vault_deposit = int(deposit_data.get("amount", 0))
                        break
            except Exception as e:
                self.logger.debug(f"No vault deposits found for user {user_id}: {e}")
            
            # Get other token balances
            token_balances = {}
            try:
                resources = await self.client.account_resources(address)
                for resource in resources:
                    if "CoinStore" in resource["type"]:
                        type_parts = resource["type"].split("<")
                        if len(type_parts) > 1:
                            token_type = type_parts[1].split(">")[0]
                            coin_data = resource["data"]["coin"]
                            balance = int(coin_data["value"])
                            
                            if balance > 0:
                                token_symbol = token_type.split("::")[-1]
                                token_balances[token_symbol] = {
                                    "balance": balance,
                                    "balance_formatted": balance / 100000000,
                                    "token_type": token_type
                                }
            except Exception as e:
                self.logger.debug(f"Error getting token balances: {e}")
            
            return {
                "status": "success",
                "apt_balance": apt_balance,
                "apt_balance_formatted": apt_balance / 100000000,
                "vault_deposit": vault_deposit,
                "vault_deposit_formatted": vault_deposit / 100000000,
                "token_balances": token_balances,
                "total_balance": apt_balance + vault_deposit,
                "address": address
            }
            
        except Exception as e:
            self.logger.error(f"Error getting balance for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def create_grid_strategy(self, user_id: str, symbol: str, base_price: float, 
                                 grid_spacing: float, num_levels: int, amount_per_level: float) -> Dict:
        """
        Create a grid trading strategy for a user
        """
        try:
            if user_id not in self.user_accounts:
                return {"status": "error", "message": "User not found"}
            
            user_account = self.user_accounts[user_id]
            
            # Convert parameters to contract units
            base_price_units = int(base_price * 1000000)
            grid_spacing_bps = int(grid_spacing * 100)  # Convert to basis points
            amount_units = int(amount_per_level * 100000000)
            
            # Prepare transaction to call create_grid_strategy on smart contract
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "create_grid_strategy",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(symbol.encode(), Serializer.to_bytes),
                    TransactionArgument(base_price_units, Serializer.u64),
                    TransactionArgument(grid_spacing_bps, Serializer.u64),
                    TransactionArgument(num_levels, Serializer.u8),
                    TransactionArgument(amount_units, Serializer.u64),
                ]
            )
            
            # Submit transaction
            txn_hash = await self._submit_transaction(user_account, payload)
            
            self.logger.info(f"Grid strategy created for {user_id}: {symbol} with {num_levels} levels")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "symbol": symbol,
                "base_price": base_price,
                "grid_spacing": grid_spacing,
                "num_levels": num_levels,
                "amount_per_level": amount_per_level
            }
        
        except Exception as e:
            self.logger.error(f"Error creating grid strategy for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def _submit_transaction(self, account: Account, payload: EntryFunction) -> str:
        """Submit a transaction to the Aptos network"""
        try:
            # Create transaction
            txn = await self.client.create_bcs_transaction(
                account,
                TransactionPayload(payload)
            )
            
            # Sign and submit
            signed_txn = account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            return txn_hash
            
        except ApiError as e:
            self.logger.error(f"API error submitting transaction: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error submitting transaction: {e}")
            raise

    def format_amount(self, amount: int) -> str:
        """Format amount from octas to APT"""
        return f"{amount / 100000000:.8f} APT"
    
    def parse_amount(self, amount_str: str) -> int:
        """Parse amount from APT to octas"""
        try:
            amount = float(amount_str)
            return int(amount * 100000000)
        except ValueError:
            return 0

    async def cleanup_user(self, user_id: str):
        """Clean up user resources"""
        try:
            # Cancel any running tasks
            if user_id in self.user_tasks:
                for strategy_name, task in self.user_tasks[user_id].items():
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                del self.user_tasks[user_id]
            
            # Remove user data
            if user_id in self.user_accounts:
                del self.user_accounts[user_id]
            if user_id in self.user_strategies:
                del self.user_strategies[user_id]
            
            self.logger.info(f"Cleaned up resources for user {user_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up user {user_id}: {e}")

    async def shutdown(self):
        """Shutdown the trading engine"""
        try:
            # Clean up all users
            user_ids = list(self.user_accounts.keys())
            for user_id in user_ids:
                await self.cleanup_user(user_id)
            
            self.logger.info("MultiUserTradingEngine shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
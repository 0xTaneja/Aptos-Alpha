"""
Base trader class for Aptos trading operations
Provides common functionality for all trading strategies
"""

from typing import Dict, List, Optional, Any
import logging
import time
import asyncio
import json
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

class BaseTrader:
    """
    Base trader class for Aptos trading operations
    Provides common functionality without circular imports
    Enhanced with agent wallet support for secure trading
    """
    
    def __init__(self, address=None, client=None, agent_account=None, contract_address=None):
        self.address = address  # Master account address for queries
        self.client = client  # Aptos RestClient
        self.agent_account = agent_account  # Agent account for signing transactions
        self.contract_address = contract_address or "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.logger = logging.getLogger(__name__)
        
        # Transaction management
        self.last_sequence_number = 0
        self.sequence_increment = 0
    
    async def get_all_token_prices(self) -> Dict[str, float]:
        """Get prices for all available tokens on Aptos"""
        try:
            # Query known DEX contracts for token prices
            prices = {}
            
            # APT price from CoinGecko (fallback to 1.0 if unavailable)
            try:
                import requests
                response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=aptos&vs_currencies=usd")
                if response.status_code == 200:
                    data = response.json()
                    prices["APT"] = data.get("aptos", {}).get("usd", 1.0)
                else:
                    prices["APT"] = 1.0
            except:
                prices["APT"] = 1.0
            
            # Query DEX contracts for other token prices
            dex_contracts = [
                "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",  # PancakeSwap
                "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af",  # Thala
            ]
            
            for contract in dex_contracts:
                try:
                    # Query TokenPairReserve resources
                    resources = await self.client.account_resources(contract)
                    for resource in resources:
                        if "TokenPairReserve" in resource["type"]:
                            # Extract token pair information and calculate price
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
                                        prices[token_x] = price_ratio * prices.get("APT", 1.0)
                                    if token_y not in prices:
                                        prices[token_y] = (1 / price_ratio) * prices.get("APT", 1.0)
                                        
                except Exception as e:
                    self.logger.debug(f"Error querying DEX contract {contract}: {e}")
                    continue
            
            # Add common stablecoins with fixed prices
            prices.update({
                "USDC": 1.0,
                "USDT": 1.0,
                "DAI": 1.0
            })
            
            return prices
            
        except Exception as e:
            self.logger.error(f"Error getting token prices: {e}")
            return {"APT": 1.0, "USDC": 1.0}
    
    async def get_user_balance(self, token_address: str = None) -> Dict:
        """
        Get user balance for specific token or APT
        Always uses master address for queries, not agent address
        """
        if not self.client or not self.address:
            return {"balance": 0, "error": "Client or address not initialized"}
        
        try:
            if not token_address or token_address.upper() == "APT":
                # Get APT balance
                balance = await self.client.account_balance(self.address)
                return {
                    "balance": balance,
                    "balance_formatted": balance / 100000000,  # Convert octas to APT
                    "token": "APT"
                }
            else:
                # Get specific token balance
                try:
                    resources = await self.client.account_resources(self.address)
                    for resource in resources:
                        if "CoinStore" in resource["type"] and token_address in resource["type"]:
                            coin_data = resource["data"]["coin"]
                            balance = int(coin_data["value"])
                            return {
                                "balance": balance,
                                "balance_formatted": balance / 100000000,  # Assuming 8 decimals
                                "token": token_address
                            }
                    
                    # Token not found
                    return {"balance": 0, "balance_formatted": 0, "token": token_address}
                    
                except Exception as e:
                    self.logger.error(f"Error getting token balance for {token_address}: {e}")
                    return {"balance": 0, "error": str(e)}
                    
        except Exception as e:
            self.logger.error(f"Error getting user balance: {e}")
            return {"balance": 0, "error": str(e)}
    
    async def get_next_sequence_number(self) -> int:
        """
        Get next sequence number for agent account transactions
        Implements proper sequence number management for agent accounts
        """
        if not self.agent_account or not self.client:
            return 0
            
        try:
            # Get current sequence number from chain
            account_info = await self.client.account(str(self.agent_account.address()))
            current_sequence = int(account_info["sequence_number"])
            
            # Ensure we don't reuse sequence numbers
            if current_sequence <= self.last_sequence_number:
                self.sequence_increment += 1
                return self.last_sequence_number + self.sequence_increment
            else:
                self.last_sequence_number = current_sequence
                self.sequence_increment = 0
                return current_sequence
                
        except Exception as e:
            self.logger.error(f"Error getting next sequence number: {e}")
            # Fallback to timestamp-based sequence
            return int(time.time() * 1000) % 1000000
    
    async def place_order_on_aptos(self, token_address: str, is_buy: bool, amount: float, 
                                  price: float, order_type: str = "limit") -> Dict:
        """
        Place order on Aptos DEX using Move contract
        """
        if not self.agent_account or not self.client:
            return {"status": "error", "message": "Agent account or client not initialized"}
            
        try:
            # Convert amounts to proper units
            amount_units = int(amount * 100000000)  # Convert to smallest unit
            price_units = int(price * 100000000)   # Convert to smallest unit
            
            # Create transaction payload for placing order
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "place_order",
                [],
                [
                    TransactionArgument(token_address, Serializer.str),
                    TransactionArgument(is_buy, Serializer.bool),
                    TransactionArgument(amount_units, Serializer.u64),
                    TransactionArgument(price_units, Serializer.u64),
                ]
            )
            
            # Create and submit transaction
            txn = await self.client.create_bcs_transaction(
                self.agent_account,
                TransactionPayload(payload)
            )
            
            signed_txn = self.agent_account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            self.logger.info(f"Order placed successfully: {txn_hash}")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "order_type": order_type,
                "token": token_address,
                "is_buy": is_buy,
                "amount": amount,
                "price": price
            }
            
        except Exception as e:
            self.logger.error(f"Error placing order on Aptos: {e}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_order_on_aptos(self, order_id: str) -> Dict:
        """Cancel order on Aptos DEX"""
        if not self.agent_account or not self.client:
            return {"status": "error", "message": "Agent account or client not initialized"}
            
        try:
            # Create transaction payload for cancelling order
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "cancel_order",
                [],
                [
                    TransactionArgument(order_id, Serializer.str),
                ]
            )
            
            # Create and submit transaction
            txn = await self.client.create_bcs_transaction(
                self.agent_account,
                TransactionPayload(payload)
            )
            
            signed_txn = self.agent_account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            self.logger.info(f"Order cancelled successfully: {txn_hash}")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "order_id": order_id
            }
            
        except Exception as e:
            self.logger.error(f"Error cancelling order on Aptos: {e}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_all_orders_on_aptos(self, token_address: str = None) -> Dict:
        """Cancel all orders for a specific token or all tokens"""
        if not self.agent_account or not self.client:
            return {"status": "error", "message": "Agent account or client not initialized"}
            
        try:
            # Create transaction payload for cancelling all orders
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "cancel_all_orders",
                [],
                [
                    TransactionArgument(token_address or "", Serializer.str),
                ]
            )
            
            # Create and submit transaction
            txn = await self.client.create_bcs_transaction(
                self.agent_account,
                TransactionPayload(payload)
            )
            
            signed_txn = self.agent_account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            self.logger.info(f"All orders cancelled successfully: {txn_hash}")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "token": token_address
            }
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders on Aptos: {e}")
            return {"status": "error", "message": str(e)}
    
    async def validate_agent_permissions(self) -> bool:
        """
        Validate that agent account has proper permissions for trading
        Returns True if agent has trading permissions
        """
        if not self.agent_account or not self.address or not self.client:
            return False
            
        try:
            # Check if agent account exists and has sufficient balance
            account_info = await self.client.account(str(self.agent_account.address()))
            balance = await self.client.account_balance(str(self.agent_account.address()))
            
            # Need at least 0.01 APT for gas
            min_balance = 1000000  # 0.01 APT in octas
            if balance < min_balance:
                self.logger.warning(f"Agent account has insufficient balance: {balance} octas")
                return False
            
            # Try to query trading contract to verify permissions
            try:
                resources = await self.client.account_resources(self.contract_address)
                # If we can query the contract, permissions are likely valid
                return True
            except Exception as e:
                self.logger.warning(f"Cannot access trading contract: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error validating agent permissions: {e}")
            return False

class AptosOptimizedTrader(BaseTrader):
    """
    Advanced trader with Aptos-specific optimizations
    Inherits from BaseTrader to avoid circular imports
    """
    
    def __init__(self, address=None, client=None, agent_account=None, contract_address=None):
        super().__init__(address, client, agent_account, contract_address)
        self.profit_history = []
        self.performance_stats = {}
        self.gas_optimization_enabled = True
    
    async def place_optimized_order(self, token_address: str, is_buy: bool, amount: float, 
                                   price: float, optimization_level: str = "standard") -> Dict:
        """
        Place order with Aptos-specific optimizations
        """
        if not self.agent_account or not self.client:
            self.logger.error("Agent account or client not initialized. Cannot place order.")
            return {"status": "error", "message": "Agent account not initialized"}
            
        try:
            # Get current gas price and optimize
            if self.gas_optimization_enabled:
                gas_unit_price = await self._get_optimal_gas_price()
            else:
                gas_unit_price = 100  # Default gas price
            
            # Validate token address format
            if not self._validate_token_address(token_address):
                return {"status": "error", "message": f"Invalid token address: {token_address}"}
            
            # Convert amounts to proper units with precision handling
            amount_units = int(amount * 100000000)  # Convert to smallest unit
            price_units = int(price * 100000000)   # Convert to smallest unit
            
            # Create optimized transaction payload
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "place_order_optimized",
                [],
                [
                    TransactionArgument(token_address, Serializer.str),
                    TransactionArgument(is_buy, Serializer.bool),
                    TransactionArgument(amount_units, Serializer.u64),
                    TransactionArgument(price_units, Serializer.u64),
                    TransactionArgument(optimization_level, Serializer.str),
                ]
            )
            
            # Create transaction with optimized gas settings
            txn = await self.client.create_bcs_transaction(
                self.agent_account,
                TransactionPayload(payload),
                max_gas_amount=10000,  # Optimized gas limit
                gas_unit_price=gas_unit_price
            )
            
            signed_txn = self.agent_account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation with timeout
            await asyncio.wait_for(
                self.client.wait_for_transaction(txn_hash),
                timeout=30.0
            )
            
            self.logger.info(f"Optimized order placed successfully: {txn_hash}")
            
            # Update performance stats
            self._update_performance_stats("order_placed", {
                "token": token_address,
                "amount": amount,
                "price": price,
                "gas_used": gas_unit_price
            })
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "order_type": "optimized",
                "token": token_address,
                "is_buy": is_buy,
                "amount": amount,
                "price": price,
                "gas_price": gas_unit_price
            }
            
        except asyncio.TimeoutError:
            self.logger.error("Transaction confirmation timeout")
            return {"status": "error", "message": "Transaction confirmation timeout"}
        except Exception as e:
            self.logger.error(f"Error placing optimized order: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_optimal_gas_price(self) -> int:
        """Get optimal gas price based on network conditions"""
        try:
            # Query network for current gas prices
            # This is a simplified implementation
            ledger_info = await self.client.ledger_info()
            
            # Base gas price with network adjustment
            base_gas_price = 100
            
            # Adjust based on network load (simplified)
            current_version = int(ledger_info["ledger_version"])
            if current_version % 1000 < 100:  # Low activity
                return base_gas_price
            elif current_version % 1000 < 500:  # Medium activity
                return int(base_gas_price * 1.2)
            else:  # High activity
                return int(base_gas_price * 1.5)
                
        except Exception as e:
            self.logger.error(f"Error getting optimal gas price: {e}")
            return 100  # Default gas price
    
    def _validate_token_address(self, token_address: str) -> bool:
        """Validate Aptos token address format"""
        if not token_address:
            return False
        
        # Basic validation for Aptos address format
        if len(token_address) < 3:
            return False
            
        if not token_address.startswith("0x") and "::" not in token_address:
            return False
            
        return True
    
    def _update_performance_stats(self, action: str, data: Dict):
        """Update performance statistics"""
        if action not in self.performance_stats:
            self.performance_stats[action] = {
                "count": 0,
                "total_gas": 0,
                "avg_gas": 0
            }
        
        stats = self.performance_stats[action]
        stats["count"] += 1
        
        if "gas_used" in data:
            stats["total_gas"] += data["gas_used"]
            stats["avg_gas"] = stats["total_gas"] / stats["count"]
    
    async def optimize_trading_params(self, token_address: str) -> Dict:
        """Optimize trading parameters based on Aptos network conditions"""
        try:
            # Get current network conditions
            ledger_info = await self.client.ledger_info()
            
            # Get token price and volatility
            prices = await self.get_all_token_prices()
            current_price = prices.get(token_address.split("::")[-1], 1.0)
            
            # Calculate optimal parameters based on network and market conditions
            optimal_size = min(0.1, current_price * 0.01)  # Size based on price
            optimal_gas_price = await self._get_optimal_gas_price()
            
            return {
                "optimal_size": optimal_size,
                "optimal_gas_price": optimal_gas_price,
                "current_price": current_price,
                "network_version": ledger_info["ledger_version"],
                "optimal_entry_timing": "immediate" if optimal_gas_price < 150 else "delayed"
            }
            
        except Exception as e:
            self.logger.error(f"Error optimizing trading parameters: {e}")
            return {
                "optimal_size": 0.1,
                "optimal_gas_price": 100,
                "optimal_entry_timing": "immediate"
            }
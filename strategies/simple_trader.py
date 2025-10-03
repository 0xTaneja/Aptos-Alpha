"""
Simple trading strategy module with direct trade execution
Converted from Hyperliquid to Aptos Move smart contracts
"""
import logging
import time
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime

# Aptos SDK imports (replacing Hyperliquid)
from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

logger = logging.getLogger(__name__)

class SimpleTrader:
    """
    Simple trading strategy for basic order execution and testing
    Provides fundamental trading operations for users using Aptos Move contracts
    """
    
    def __init__(self, client: RestClient = None, account: Account = None, contract_address: str = None):
        if client and account:
            self.client = client
            self.account = account
            self.address = str(account.address())
        else:
            # Default Aptos testnet setup
            self.client = RestClient("https://fullnode.testnet.aptoslabs.com/v1")
            # Account will be set by the calling code
            self.account = None
            self.address = None
        
        # Contract address for trading engine
        self.contract_address = contract_address or "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.user_manager = None
        
        logger.info("SimpleTrader initialized with Aptos SDK")
    
    async def validate_connection(self) -> bool:
        """Validate connection to Aptos network"""
        try:
            if not self.client:
                return False
            
            # Test connection by getting chain info
            chain_info = await self.client.info()
            return chain_info is not None
            
        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return False
    
    async def place_market_order(self, coin: str, is_buy: bool, size: float) -> Dict:
        """
        Place a market order using Aptos Move contracts
        
        Args:
            coin: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            
        Returns:
            Dict with order result
        """
        try:
            if not self.account:
                return {'status': 'error', 'message': 'No account configured'}
            
            # Get current market price for market order
            current_price = await self._get_asset_price(coin)
            if current_price <= 0:
                return {'status': 'error', 'message': f'No price data for {coin}'}
            
            # Use current price for market order execution
            result = await self._place_order_on_aptos(
                coin, "buy" if is_buy else "sell", size, current_price
            )
            
            return {
                'status': result.get('status', 'error'),
                'result': result,
                'coin': coin,
                'side': 'buy' if is_buy else 'sell',
                'size': size,
                'price': current_price,
                'type': 'market'
            }
            
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def place_limit_order(self, coin: str, is_buy: bool, size: float, price: float, post_only: bool = False) -> Dict:
        """
        Place a limit order using Aptos Move contracts
        
        Args:
            coin: Asset symbol
            is_buy: True for buy, False for sell
            size: Order size
            price: Order price
            post_only: True for post-only (maker) orders
            
        Returns:
            Dict with order result
        """
        try:
            if not self.account:
                return {'status': 'error', 'message': 'No account configured'}
            
            # Place limit order using Aptos Move contract
            result = await self._place_order_on_aptos(
                coin, "buy" if is_buy else "sell", size, price
            )
            
            return {
                'status': result.get('status', 'error'),
                'result': result,
                'coin': coin,
                'side': 'buy' if is_buy else 'sell',
                'size': size,
                'price': price,
                'type': 'limit',
                'post_only': post_only
            }
            
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def place_test_order(self, coin: str = "BTC") -> Dict:
        """Place test order using Aptos Move contracts"""
        try:
            # Get realistic price from Aptos
            try:
                current_price = await self._get_asset_price(coin)
                test_price = current_price * 0.9  # 10% below market
            except:
                test_price = 25000  # Fallback price
            
            # Place test order using Aptos Move contract
            result = await self._place_order_on_aptos(
                coin, "buy", 0.001, test_price
            )
            
            logger.info(f"Test order result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error placing test order: {e}")
            return {"status": "error", "message": str(e)}

    async def place_grid_order(self, coin: str, is_buy: bool, size: float, 
                              price: float) -> Dict:
        """Place grid order using Aptos Move contracts"""
        try:
            # Place grid order using Aptos Move contract
            result = await self._place_order_on_aptos(
                coin, "buy" if is_buy else "sell", size, price
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error placing grid order: {e}")
            return {"status": "error", "message": str(e)}

    async def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel a specific order using Aptos Move contracts
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Dict with cancellation result
        """
        try:
            if not self.account:
                return {'status': 'error', 'message': 'No account configured'}
            
            result = await self._cancel_order_on_aptos(order_id)
            
            return {
                'status': result.get('status', 'error'),
                'result': result,
                'order_id': order_id
            }
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def cancel_all_orders(self, coin: str) -> Dict:
        """
        Cancel all orders for a specific coin using Aptos Move contracts
        
        Args:
            coin: Asset symbol
            
        Returns:
            Dict with cancellation result
        """
        try:
            if not self.account:
                return {'status': 'error', 'message': 'No account configured'}
            
            # Get all orders for this coin and cancel them
            orders = await self._get_user_orders(coin)
            cancelled_count = 0
            
            for order in orders:
                order_id = order.get('order_id')
                if order_id:
                    result = await self._cancel_order_on_aptos(order_id)
                    if result.get('status') == 'success':
                        cancelled_count += 1
            
            return {
                'status': 'success',
                'coin': coin,
                'cancelled_orders': cancelled_count,
                'total_orders': len(orders)
            }
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def get_current_price(self, coin: str) -> Optional[float]:
        """
        Get current market price for a coin from Aptos
        
        Args:
            coin: Asset symbol
            
        Returns:
            Current price or None if error
        """
        try:
            price = await self._get_asset_price(coin)
            return price if price > 0 else None
            
        except Exception as e:
            logger.error(f"Error getting current price for {coin}: {e}")
            return None
    
    async def get_order_book(self, coin: str) -> Optional[Dict]:
        """
        Get order book for a coin from Aptos DEX
        
        Args:
            coin: Asset symbol
            
        Returns:
            Order book data or None if error
        """
        try:
            return await self._get_orderbook(coin)
            
        except Exception as e:
            logger.error(f"Error getting order book for {coin}: {e}")
            return None
    
    def set_user_manager(self, user_manager):
        """Set user manager for multi-user support"""
        self.user_manager = user_manager
        logger.info("User manager set for SimpleTrader")

    # ========== APTOS HELPER METHODS ==========
    
    async def _get_asset_price(self, coin: str) -> float:
        """Get current asset price from Aptos oracle or price feed"""
        try:
            # Query real Aptos price oracle
            if coin == "APT":
                # Get APT price from CoinGecko API
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=aptos&vs_currencies=usd") as response:
                        if response.status == 200:
                            data = await response.json()
                            return float(data.get("aptos", {}).get("usd", 0))
            
            # For other tokens, query Aptos DEX aggregators
            dex_contracts = [
                "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",  # PancakeSwap
                "0x61d2c22a6cb7831bee0f48363b0eec92369357aece0d1142062f7d5d85c7bef8",  # Thala
            ]
            
            for contract in dex_contracts:
                try:
                    # Query price from DEX contract
                    resource_type = f"{contract}::swap::TokenPairReserve<{coin}, 0x1::aptos_coin::AptosCoin>"
                    resource = await self.client.account_resource(contract, resource_type)
                    
                    if resource:
                        reserve_x = int(resource["data"]["reserve_x"])
                        reserve_y = int(resource["data"]["reserve_y"])
                        
                        if reserve_x > 0 and reserve_y > 0:
                            # Calculate price from reserves
                            price = (reserve_y / 100000000) / (reserve_x / 100000000)  # Convert from octas
                            return price
                            
                except Exception:
                    continue
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting asset price for {coin}: {e}")
            return 0.0
    
    async def _place_order_on_aptos(self, coin: str, side: str, size: float, price: float) -> Dict:
        """Place order using Aptos Move smart contract"""
        try:
            if not self.account:
                return {'status': 'error', 'message': 'No account configured'}
            
            # Convert to Move contract call
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "place_order",
                [],
                [coin, side, int(size * 100000000), int(price * 100)]  # Convert to appropriate units
            )
            
            # Submit transaction
            txn_request = await self.client.create_bcs_transaction(self.account, payload)
            signed_txn = self.account.sign(txn_request)
            tx_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for transaction
            await self.client.wait_for_transaction(tx_hash)
            
            # Generate order ID (in production this would come from the contract)
            order_id = f"{coin}_{side}_{int(time.time() * 1000)}"
            
            return {
                'status': 'success',
                'tx_hash': tx_hash,
                'order_id': order_id
            }
            
        except Exception as e:
            logger.error(f"Error placing order on Aptos: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _cancel_order_on_aptos(self, order_id: str) -> Dict:
        """Cancel order using Aptos Move smart contract"""
        try:
            if not self.account:
                return {'status': 'error', 'message': 'No account configured'}
            
            # Convert to Move contract call
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "cancel_order",
                [],
                [order_id]
            )
            
            # Submit transaction
            txn_request = await self.client.create_bcs_transaction(self.account, payload)
            signed_txn = self.account.sign(txn_request)
            tx_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for transaction
            await self.client.wait_for_transaction(tx_hash)
            
            return {
                'status': 'success',
                'tx_hash': tx_hash
            }
            
        except Exception as e:
            logger.error(f"Error cancelling order on Aptos: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _get_orderbook(self, coin: str) -> Dict:
        """Get orderbook from Aptos DEX"""
        try:
            # Query real orderbook from Aptos DEX contracts
            dex_contracts = [
                "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",  # PancakeSwap
                "0x61d2c22a6cb7831bee0f48363b0eec92369357aece0d1142062f7d5d85c7bef8",  # Thala
            ]
            
            for contract in dex_contracts:
                try:
                    # Query orderbook from DEX contract
                    orderbook_resource = f"{contract}::orderbook::OrderBook<{coin}, 0x1::aptos_coin::AptosCoin>"
                    resource = await self.client.account_resource(contract, orderbook_resource)
                    
                    if resource and "data" in resource:
                        data = resource["data"]
                        
                        # Extract bids and asks from the orderbook
                        bids = []
                        asks = []
                        
                        # Parse bid orders
                        if "bids" in data:
                            for bid in data["bids"]:
                                bids.append({
                                    'price': float(bid.get("price", 0)) / 100000000,  # Convert from octas
                                    'size': float(bid.get("quantity", 0)) / 100000000
                                })
                        
                        # Parse ask orders  
                        if "asks" in data:
                            for ask in data["asks"]:
                                asks.append({
                                    'price': float(ask.get("price", 0)) / 100000000,  # Convert from octas
                                    'size': float(ask.get("quantity", 0)) / 100000000
                                })
                        
                        if bids or asks:
                            return {
                                'bids': sorted(bids, key=lambda x: x['price'], reverse=True),
                                'asks': sorted(asks, key=lambda x: x['price'])
                            }
                            
                except Exception:
                    continue
            
            # Fallback: try to get from AMM pool reserves
            try:
                mid_price = await self._get_asset_price(coin)
                if mid_price > 0:
                    # Create synthetic orderbook from AMM
                    bids = []
                    asks = []
                    
                    # Generate orders around current price with realistic spreads
                    spread = 0.001  # 0.1% spread
                    
                    for i in range(1, 6):  # 5 levels each side
                        bid_price = mid_price * (1 - spread * i)
                        ask_price = mid_price * (1 + spread * i)
                        
                        # Size decreases with distance from mid
                        size = 100.0 / i  # Decreasing liquidity
                        
                        bids.append({'price': bid_price, 'size': size})
                        asks.append({'price': ask_price, 'size': size})
                    
                    return {'bids': bids, 'asks': asks}
            except Exception:
                pass
            
            return {'bids': [], 'asks': []}
            
        except Exception as e:
            logger.error(f"Error getting orderbook: {e}")
            return {'bids': [], 'asks': []}
    
    async def _get_user_orders(self, coin: str) -> list:
        """Get user's active orders for a specific coin"""
        try:
            if not self.account:
                return []
            
            # Query user's active orders from Aptos trading contract
            try:
                user_orders_resource = f"{self.contract_address}::trading_engine::UserOrders"
                resource = await self.client.account_resource(self.account.address(), user_orders_resource)
                
                if resource and "data" in resource:
                    orders = resource["data"].get("orders", [])
                    
                    # Filter orders for the specific coin
                    coin_orders = []
                    for order in orders:
                        if order.get("coin") == coin and order.get("status") == "active":
                            coin_orders.append({
                                'order_id': order.get("id"),
                                'side': order.get("side"),
                                'size': float(order.get("size", 0)) / 100000000,
                                'price': float(order.get("price", 0)) / 100000000,
                                'status': order.get("status")
                            })
                    
                    return coin_orders
                    
            except Exception:
                # If user orders resource doesn't exist, return empty list
                return []
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return []
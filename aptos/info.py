"""
Aptos Info - Market data and account information for Aptos Alpha Bot
Equivalent to Hyperliquid's info.py but for Aptos blockchain
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal

import aiohttp

from .api import AptosAPI

logger = logging.getLogger(__name__)

class AptosInfo(AptosAPI):
    """
    Information and market data class for Aptos blockchain
    Handles price feeds, account data, and DEX information
    """
    
    def __init__(self, node_url: Optional[str] = None, use_hyperion: bool = True):
        super().__init__(node_url)
        
        # Coin mappings
        self.coin_to_symbol = {
            "0x1::aptos_coin::AptosCoin": "APT",
            "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDC": "USDC",
            "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDT": "USDT",
        }
        
        self.symbol_to_coin = {v: k for k, v in self.coin_to_symbol.items()}
        
        # DEX contract mappings
        self.dex_contracts = {
            "pancakeswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",
            "thala": "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af",
            "liquidswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12"
        }
        
        # Sponsor integrations
        self.use_hyperion_oracle = use_hyperion  # Hyperion for better price data
        self.hyperion_api = "https://api.hyperion.xyz/v1"  # Placeholder URL
        
        # Price cache
        self._price_cache = {}
        self._cache_expiry = {}
        self.cache_duration = 30  # 30 seconds
        
        logger.info(f"Initialized Aptos Info (Hyperion Oracle: {use_hyperion})")
    
    async def get_account_balance(self, address: str, coin_type: str = None) -> int:
        """Get account balance for specific coin"""
        coin_type = coin_type or "0x1::aptos_coin::AptosCoin"
        
        # Try method 1: Direct resource query
        try:
            resource_type = f"0x1::coin::CoinStore<{coin_type}>"
            resource = await self.client.account_resource(address, resource_type)
            balance = int(resource["data"]["coin"]["value"])
            return balance
        except Exception as e:
            logger.debug(f"CoinStore not found via account_resource: {e}")
        
        # Try method 2: Query all resources
        try:
            resources = await self.client.account_resources(address)
            for resource in resources:
                if "0x1::coin::CoinStore" in resource["type"] and coin_type.split("::")[-1] in resource["type"]:
                    balance = int(resource["data"]["coin"]["value"])
                    logger.info(f"Found balance via account_resources: {balance / 100000000:.8f} APT")
                    return balance
        except Exception as e:
            logger.debug(f"Error querying account_resources: {e}")
        
        # Try method 3: Use Indexer GraphQL API (what the explorer uses)
        try:
            indexer_url = "https://api.testnet.aptoslabs.com/v1/graphql"
            query = """
            query GetCoinBalances($owner_address: String!) {
              current_fungible_asset_balances(
                where: {owner_address: {_eq: $owner_address}}
              ) {
                amount
                asset_type
              }
            }
            """
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    indexer_url,
                    json={"query": query, "variables": {"owner_address": address}},
                    headers={"Content-Type": "application/json"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        balances = data.get("data", {}).get("current_fungible_asset_balances", [])
                        for balance_entry in balances:
                            if balance_entry.get("asset_type") == coin_type:
                                balance = int(balance_entry["amount"])
                                logger.info(f"Found balance via Indexer API: {balance / 100000000:.8f} APT")
                                return balance
        except Exception as e:
            logger.debug(f"Error querying Indexer API: {e}")
        
        # Account has no balance
        logger.debug(f"Account {address} has no {coin_type} balance")
        return 0
    
    async def get_all_balances(self, address: str) -> Dict[str, int]:
        """Get all coin balances for an account"""
        try:
            resources = await self.get_account_resources(address)
            balances = {}
            
            for resource in resources:
                if "CoinStore" in resource.get("type", ""):
                    coin_type = resource["type"].split("<")[1].split(">")[0]
                    balance = int(resource["data"]["coin"]["value"])
                    symbol = self.coin_to_symbol.get(coin_type, coin_type)
                    balances[symbol] = balance
            
            return balances
        except Exception as e:
            logger.error(f"Error getting all balances for {address}: {e}")
            return {}
    
    async def get_apt_price_usd(self) -> float:
        """Get APT price in USD from CoinGecko"""
        try:
            cache_key = "apt_usd"
            if self._is_cached(cache_key):
                return self._price_cache[cache_key]
            
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/simple/price?ids=aptos&vs_currencies=usd"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = float(data["aptos"]["usd"])
                        self._cache_price(cache_key, price)
                        return price
            
            return 0.0
        except Exception as e:
            logger.error(f"Error getting APT price: {e}")
            return 0.0
    
    async def get_pair_price(self, coin_a: str, coin_b: str, dex: str = None) -> float:
        """Get current price for a trading pair"""
        try:
            cache_key = f"{coin_a}_{coin_b}_{dex or 'default'}"
            if self._is_cached(cache_key):
                return self._price_cache[cache_key]
            
            # For APT/USD pairs, use CoinGecko
            if coin_a == "0x1::aptos_coin::AptosCoin" and "USD" in coin_b:
                price = await self.get_apt_price_usd()
                self._cache_price(cache_key, price)
                return price
            
            # For other pairs, query DEX reserves
            reserves_a, reserves_b = await self.get_pair_reserves(coin_a, coin_b, dex)
            if reserves_a > 0 and reserves_b > 0:
                price = reserves_b / reserves_a
                self._cache_price(cache_key, price)
                return price
            
            return 0.0
        except Exception as e:
            logger.error(f"Error getting pair price {coin_a}/{coin_b}: {e}")
            return 0.0
    
    async def get_pair_reserves(self, coin_a: str, coin_b: str, dex: str = None) -> Tuple[int, int]:
        """Get liquidity pool reserves for a trading pair"""
        try:
            dex_contract = self.dex_contracts.get(dex or "pancakeswap")
            
            # Query the DEX contract for pool information
            # This is a simplified implementation - actual implementation would
            # depend on the specific DEX contract structure
            
            # For now, return mock reserves based on typical pool sizes
            if coin_a == "0x1::aptos_coin::AptosCoin":
                return (1000000000000, 10000000000)  # 10k APT, 100k USDC
            else:
                return (10000000000, 1000000000000)  # 100k USDC, 10k APT
                
        except Exception as e:
            logger.error(f"Error getting pair reserves {coin_a}/{coin_b}: {e}")
            return (0, 0)
    
    async def get_pool_info(self, coin_a: str, coin_b: str, dex: str = None) -> Dict:
        """Get detailed pool information"""
        try:
            reserves_a, reserves_b = await self.get_pair_reserves(coin_a, coin_b, dex)
            price = await self.get_pair_price(coin_a, coin_b, dex)
            
            return {
                "coin_a": coin_a,
                "coin_b": coin_b,
                "reserves_a": reserves_a,
                "reserves_b": reserves_b,
                "price": price,
                "dex": dex or "pancakeswap",
                "total_liquidity": reserves_a + reserves_b,
                "timestamp": int(time.time())
            }
        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return {}
    
    async def get_all_pools(self, dex: str = None) -> List[Dict]:
        """Get information for all available pools"""
        try:
            # Common trading pairs on Aptos
            pairs = [
                ("0x1::aptos_coin::AptosCoin", "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDC"),
                ("0x1::aptos_coin::AptosCoin", "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDT"),
                ("0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDC", "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDT"),
            ]
            
            pools = []
            for coin_a, coin_b in pairs:
                pool_info = await self.get_pool_info(coin_a, coin_b, dex)
                if pool_info:
                    pools.append(pool_info)
            
            return pools
        except Exception as e:
            logger.error(f"Error getting all pools: {e}")
            return []
    
    async def get_account_portfolio(self, address: str) -> Dict:
        """Get complete portfolio information for an account"""
        try:
            balances = await self.get_all_balances(address)
            apt_price = await self.get_apt_price_usd()
            
            portfolio = {
                "address": address,
                "balances": balances,
                "total_value_usd": 0.0,
                "positions": [],
                "timestamp": int(time.time())
            }
            
            # Calculate total portfolio value
            for symbol, balance in balances.items():
                if symbol == "APT":
                    value_usd = (balance / 100000000) * apt_price  # Convert octas to APT
                    portfolio["total_value_usd"] += value_usd
                    portfolio["positions"].append({
                        "symbol": symbol,
                        "balance": balance,
                        "balance_formatted": balance / 100000000,
                        "price_usd": apt_price,
                        "value_usd": value_usd
                    })
                elif symbol in ["USDC", "USDT"]:
                    value_usd = balance / 1000000  # Assuming 6 decimals for stablecoins
                    portfolio["total_value_usd"] += value_usd
                    portfolio["positions"].append({
                        "symbol": symbol,
                        "balance": balance,
                        "balance_formatted": balance / 1000000,
                        "price_usd": 1.0,
                        "value_usd": value_usd
                    })
            
            return portfolio
        except Exception as e:
            logger.error(f"Error getting portfolio for {address}: {e}")
            return {}
    
    async def get_user_vault_deposit(self, vault_owner: str, user_address: str) -> int:
        """Get user's deposit amount in the trading vault"""
        try:
            # Query the TradingVault resource to get user deposits
            resource_type = f"{vault_owner}::trading_vault::TradingVault"
            resource = await self.client.account_resource(vault_owner, resource_type)
            
            # Find user in the vault's user_addresses list
            user_addresses = resource["data"].get("user_addresses", [])
            user_deposits = resource["data"].get("user_deposits", [])
            
            for i, addr in enumerate(user_addresses):
                if addr.lower() == user_address.lower():
                    return int(user_deposits[i].get("amount", 0))
            
            return 0  # User has no deposit
        except Exception as e:
            logger.debug(f"No vault deposit found for {user_address} in vault {vault_owner}: {e}")
            return 0
    
    async def get_transaction_details(self, txn_hash: str) -> Dict:
        """Get detailed transaction information"""
        try:
            txn = await self.get_transaction_by_hash(txn_hash)
            if not txn:
                return {}
            
            return {
                "hash": txn_hash,
                "sender": txn.get("sender"),
                "sequence_number": txn.get("sequence_number"),
                "gas_used": txn.get("gas_used"),
                "gas_unit_price": txn.get("gas_unit_price"),
                "success": txn.get("success"),
                "timestamp": txn.get("timestamp"),
                "type": txn.get("type"),
                "payload": txn.get("payload"),
                "events": txn.get("events", [])
            }
        except Exception as e:
            logger.error(f"Error getting transaction details for {txn_hash}: {e}")
            return {}
    
    async def get_staking_info(self, address: str) -> Dict:
        """Get staking information for an account"""
        try:
            # Query staking-related resources
            resources = await self.get_account_resources(address)
            staking_info = {
                "total_staked": 0,
                "active_stake": 0,
                "pending_inactive": 0,
                "rewards": 0,
                "validators": [],
                "timestamp": int(time.time())
            }
            
            # Parse staking resources
            for resource in resources:
                resource_type = resource.get("type", "")
                if "stake" in resource_type.lower():
                    # Extract staking information
                    data = resource.get("data", {})
                    if "active" in data:
                        staking_info["active_stake"] += int(data.get("active", {}).get("value", 0))
                    if "pending_inactive" in data:
                        staking_info["pending_inactive"] += int(data.get("pending_inactive", {}).get("value", 0))
            
            staking_info["total_staked"] = staking_info["active_stake"] + staking_info["pending_inactive"]
            
            return staking_info
        except Exception as e:
            logger.error(f"Error getting staking info for {address}: {e}")
            return {}
    
    def _is_cached(self, key: str) -> bool:
        """Check if price is cached and not expired"""
        if key not in self._price_cache:
            return False
        
        if key not in self._cache_expiry:
            return False
        
        return time.time() < self._cache_expiry[key]
    
    def _cache_price(self, key: str, price: float):
        """Cache price with expiry"""
        self._price_cache[key] = price
        self._cache_expiry[key] = time.time() + self.cache_duration
    
    def get_coin_symbol(self, coin_type: str) -> str:
        """Get symbol for coin type"""
        return self.coin_to_symbol.get(coin_type, coin_type)
    
    def get_coin_type(self, symbol: str) -> str:
        """Get coin type for symbol"""
        return self.symbol_to_coin.get(symbol, symbol)
    
    async def close(self):
        """Clean up resources"""
        await super().close()
        logger.info("Aptos Info closed")

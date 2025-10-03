"""
Aptos Exchange - Core trading functionality for Aptos Alpha Bot
Equivalent to Hyperliquid's exchange.py but for Aptos blockchain
"""

import json
import logging
import asyncio
import time
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)
from aptos_sdk.type_tag import TypeTag, StructTag
from aptos_sdk.bcs import Serializer as BCSSerializer

from .api import AptosAPI
from .info import AptosInfo

logger = logging.getLogger(__name__)

class AptosExchange(AptosAPI):
    """
    Main Aptos exchange class for trading operations
    Handles DEX interactions, order placement, and portfolio management
    """
    
    # Default slippage for market orders (5%)
    DEFAULT_SLIPPAGE = 0.05
    
    # Aptos coin type constants
    APT_COIN_TYPE = "0x1::aptos_coin::AptosCoin"
    USDC_COIN_TYPE = "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDC"
    USDT_COIN_TYPE = "0xf22bede237a07e121b56d91a491eb7bcdfd1f5907926a9e58338f964a01b17fa::asset::USDT"
    
    # DEX contract addresses
    PANCAKESWAP_CONTRACT = "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12"
    THALA_CONTRACT = "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af"
    LIQUIDSWAP_CONTRACT = "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12"
    
    # Sponsor integrations - DEX Aggregators
    PANORA_AGGREGATOR = "panora"  # Best price routing across all DEXs
    EKUBO_DEX = "ekubo"  # Additional AMM option
    
    def __init__(
        self,
        account: Account,
        node_url: Optional[str] = None,
        vault_address: Optional[str] = None,
        preferred_dex: str = "pancakeswap",
        config: Dict = None
    ):
        super().__init__(node_url)
        self.account = account
        self.vault_address = vault_address
        self.preferred_dex = preferred_dex
        self.info = AptosInfo(node_url)
        self.config = config or {}
        
        # Gas configuration
        self.default_gas_unit_price = 100
        self.max_gas_amount = 10000
        
        # Sponsor integrations configuration
        self.sponsor_config = self.config.get("trading", {}).get("sponsor_integrations", {})
        self.panora_enabled = self.sponsor_config.get("panora", {}).get("enabled", False)
        self.panora_api_url = self.sponsor_config.get("panora", {}).get("api_url", "https://api.panora.exchange")
        self.panora_api_key = self.sponsor_config.get("panora", {}).get("api_key", "")
        
        # HTTP session for API calls
        self._session = None
        
        logger.info(f"Initialized Aptos Exchange for account: {self.account.address()}")
        if self.panora_enabled:
            logger.info("✅ Panora DEX Aggregator ENABLED for best price routing")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for API calls"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _get_panora_quote(
        self,
        from_token: str,
        to_token: str,
        amount: int,
        slippage: float = 0.01
    ) -> Dict:
        """
        Get best swap quote from Panora Aggregator
        Compares prices across all DEXs and returns optimal route
        """
        if not self.panora_enabled:
            return {"success": False, "error": "Panora not enabled"}
        
        try:
            session = await self._get_session()
            url = f"{self.panora_api_url}/swap"
            
            headers = {
                "x-api-key": self.panora_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "fromToken": from_token,
                "toToken": to_token,
                "fromTokenAmount": str(amount),
                "slippagePercentage": slippage * 100,
                "userAddress": str(self.account.address())
            }
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract quote information
                    quote = data.get("quotes", [{}])[0] if data.get("quotes") else {}
                    
                    logger.info(f"🎯 Panora Quote: {amount} {from_token} → {quote.get('toTokenAmount', 0)} {to_token}")
                    logger.info(f"📊 Best Route: {' → '.join(quote.get('route', []))}")
                    logger.info(f"💰 Price Impact: {quote.get('priceImpact', 0)}%")
                    
                    return {
                        "success": True,
                        "from_amount": amount,
                        "to_amount": int(quote.get("toTokenAmount", 0)),
                        "price_impact": float(quote.get("priceImpact", 0)),
                        "route": quote.get("route", []),
                        "dex_breakdown": quote.get("dexBreakdown", []),
                        "tx_data": quote.get("txData"),
                        "gas_estimate": quote.get("gasEstimate"),
                        "fee_token_amount": quote.get("feeTokenAmount", 0)
                    }
                else:
                    error_text = await response.text()
                    logger.warning(f"Panora API error {response.status}: {error_text}")
                    return {"success": False, "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Panora quote error: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_dex_contract(self, dex_name: str = None) -> str:
        """Get DEX contract address"""
        dex = dex_name or self.preferred_dex
        contracts = {
            "pancakeswap": self.PANCAKESWAP_CONTRACT,
            "thala": self.THALA_CONTRACT,
            "liquidswap": self.LIQUIDSWAP_CONTRACT,
            "hyperion": self.sponsor_config.get("hyperion", {}).get("contract_testnet", self.PANCAKESWAP_CONTRACT)
        }
        return contracts.get(dex.lower(), self.PANCAKESWAP_CONTRACT)
    
    async def _submit_transaction(self, payload: TransactionPayload) -> str:
        """Submit transaction to Aptos network"""
        try:
            # Create transaction
            txn = await self.client.create_bcs_transaction(
                sender=self.account,
                payload=payload,
                gas_unit_price=self.default_gas_unit_price,
                max_gas_amount=self.max_gas_amount
            )
            
            # Sign and submit
            signed_txn = self.account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            logger.info(f"Transaction submitted successfully: {txn_hash}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise
    
    async def get_account_balance(self, coin_type: str = None) -> int:
        """Get account balance for specific coin type"""
        try:
            from aptos_sdk.account_address import AccountAddress
            coin_type = coin_type or self.APT_COIN_TYPE
            address_obj = AccountAddress.from_str(str(self.account.address()))
            balance = await self.client.account_balance(address_obj, coin_type=coin_type)
            return balance
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0
    
    async def get_all_balances(self) -> Dict[str, int]:
        """Get all coin balances for the account"""
        try:
            resources = await self.client.account_resources(str(self.account.address()))
            balances = {}
            
            for resource in resources:
                if "CoinStore" in resource["type"]:
                    coin_type = resource["type"].split("<")[1].split(">")[0]
                    balance = int(resource["data"]["coin"]["value"])
                    balances[coin_type] = balance
            
            return balances
        except Exception as e:
            logger.error(f"Error getting all balances: {e}")
            return {}
    
    async def swap_exact_input(
        self,
        from_coin: str,
        to_coin: str,
        amount_in: int,
        min_amount_out: int = 0,
        dex: str = None
    ) -> str:
        """
        Swap exact input amount for output tokens
        Equivalent to market buy/sell orders
        """
        try:
            dex_contract = self._get_dex_contract(dex)
            
            # Create swap transaction payload
            payload = EntryFunction.natural(
                f"{dex_contract}::router",
                "swap_exact_input",
                [TypeTag(StructTag.from_str(from_coin)), TypeTag(StructTag.from_str(to_coin))],
                [
                    TransactionArgument(amount_in, Serializer.u64),
                    TransactionArgument(min_amount_out, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(TransactionPayload(payload))
            
            logger.info(f"Swap executed: {amount_in} {from_coin} -> {to_coin} on {dex}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"Swap failed: {e}")
            raise
    
    async def swap_exact_output(
        self,
        from_coin: str,
        to_coin: str,
        amount_out: int,
        max_amount_in: int,
        dex: str = None
    ) -> str:
        """
        Swap for exact output amount
        """
        try:
            dex_contract = self._get_dex_contract(dex)
            
            payload = EntryFunction.natural(
                f"{dex_contract}::router",
                "swap_exact_output",
                [TypeTag(StructTag.from_str(from_coin)), TypeTag(StructTag.from_str(to_coin))],
                [
                    TransactionArgument(amount_out, Serializer.u64),
                    TransactionArgument(max_amount_in, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(TransactionPayload(payload))
            
            logger.info(f"Exact output swap: {from_coin} -> {amount_out} {to_coin} on {dex}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"Exact output swap failed: {e}")
            raise
    
    async def add_liquidity(
        self,
        coin_a: str,
        coin_b: str,
        amount_a: int,
        amount_b: int,
        min_a: int = 0,
        min_b: int = 0,
        dex: str = None
    ) -> str:
        """Add liquidity to a trading pair"""
        try:
            dex_contract = self._get_dex_contract(dex)
            
            payload = EntryFunction.natural(
                f"{dex_contract}::router",
                "add_liquidity",
                [TypeTag(StructTag.from_str(coin_a)), TypeTag(StructTag.from_str(coin_b))],
                [
                    TransactionArgument(amount_a, Serializer.u64),
                    TransactionArgument(amount_b, Serializer.u64),
                    TransactionArgument(min_a, Serializer.u64),
                    TransactionArgument(min_b, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(TransactionPayload(payload))
            
            logger.info(f"Liquidity added: {amount_a} {coin_a} + {amount_b} {coin_b} on {dex}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"Add liquidity failed: {e}")
            raise
    
    async def remove_liquidity(
        self,
        coin_a: str,
        coin_b: str,
        liquidity_amount: int,
        min_a: int = 0,
        min_b: int = 0,
        dex: str = None
    ) -> str:
        """Remove liquidity from a trading pair"""
        try:
            dex_contract = self._get_dex_contract(dex)
            
            payload = EntryFunction.natural(
                f"{dex_contract}::router",
                "remove_liquidity",
                [TypeTag(StructTag.from_str(coin_a)), TypeTag(StructTag.from_str(coin_b))],
                [
                    TransactionArgument(liquidity_amount, Serializer.u64),
                    TransactionArgument(min_a, Serializer.u64),
                    TransactionArgument(min_b, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(TransactionPayload(payload))
            
            logger.info(f"Liquidity removed: {liquidity_amount} LP tokens from {coin_a}/{coin_b} on {dex}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"Remove liquidity failed: {e}")
            raise
    
    async def transfer_apt(self, to_address: str, amount: int) -> str:
        """Transfer APT to another address"""
        try:
            payload = EntryFunction.natural(
                "0x1::aptos_account",
                "transfer",
                [],
                [
                    TransactionArgument(to_address, Serializer.str),
                    TransactionArgument(amount, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(TransactionPayload(payload))
            
            logger.info(f"Transferred {amount} octas to {to_address}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"APT transfer failed: {e}")
            raise
    
    async def transfer_coin(self, to_address: str, amount: int, coin_type: str) -> str:
        """Transfer any coin type to another address"""
        try:
            payload = EntryFunction.natural(
                "0x1::coin",
                "transfer",
                [TypeTag(StructTag.from_str(coin_type))],
                [
                    TransactionArgument(to_address, Serializer.str),
                    TransactionArgument(amount, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(TransactionPayload(payload))
            
            logger.info(f"Transferred {amount} {coin_type} to {to_address}")
            return txn_hash
            
        except Exception as e:
            logger.error(f"Coin transfer failed: {e}")
            raise
    
    async def get_pair_price(self, coin_a: str, coin_b: str, dex: str = None) -> float:
        """Get current price for a trading pair"""
        try:
            # This would query the DEX for current price
            # Implementation depends on specific DEX API
            return await self.info.get_pair_price(coin_a, coin_b, dex)
        except Exception as e:
            logger.error(f"Error getting pair price: {e}")
            return 0.0
    
    async def get_pair_reserves(self, coin_a: str, coin_b: str, dex: str = None) -> Tuple[int, int]:
        """Get liquidity pool reserves for a trading pair"""
        try:
            return await self.info.get_pair_reserves(coin_a, coin_b, dex)
        except Exception as e:
            logger.error(f"Error getting pair reserves: {e}")
            return (0, 0)
    
    async def calculate_slippage_price(
        self,
        coin_a: str,
        coin_b: str,
        is_buy: bool,
        slippage: float = None,
        current_price: float = None
    ) -> float:
        """Calculate price with slippage protection"""
        try:
            slippage = slippage or self.DEFAULT_SLIPPAGE
            
            if not current_price:
                current_price = await self.get_pair_price(coin_a, coin_b)
            
            if is_buy:
                # For buy orders, increase price by slippage
                return current_price * (1 + slippage)
            else:
                # For sell orders, decrease price by slippage
                return current_price * (1 - slippage)
                
        except Exception as e:
            logger.error(f"Error calculating slippage price: {e}")
            return current_price or 0.0
    
    async def market_buy(
        self,
        base_coin: str,
        quote_coin: str,
        quote_amount: int,
        slippage: float = None,
        dex: str = None,
        use_aggregator: bool = True
    ) -> Dict:
        """
        Execute market buy order
        If use_aggregator=True and Panora is enabled, uses aggregator for best price routing
        Returns: Dict with txn_hash and routing info
        """
        try:
            slippage = slippage or self.DEFAULT_SLIPPAGE
            
            # Try Panora aggregator first if enabled
            if use_aggregator and self.panora_enabled:
                logger.info("🎯 Using Panora Aggregator for best price routing...")
                panora_quote = await self._get_panora_quote(quote_coin, base_coin, quote_amount, slippage)
                
                if panora_quote.get("success"):
                    logger.info(f"✅ Panora route: {' → '.join(panora_quote.get('route', []))} | Impact: {panora_quote.get('price_impact', 0)}%")
                    
                    # Use Panora's calculated output
                    min_output = panora_quote["to_amount"]
                    
                    # Execute swap on best DEX from route
                    if panora_quote.get("route"):
                        best_dex = panora_quote["route"][0].lower()
                        dex = best_dex if best_dex in ["pancakeswap", "thala", "liquidswap", "hyperion"] else dex
                    
                    txn_hash = await self.swap_exact_input(
                        from_coin=quote_coin,
                        to_coin=base_coin,
                        amount_in=quote_amount,
                        min_amount_out=min_output,
                        dex=dex
                    )
                    
                    return {
                        "success": True,
                        "txn_hash": txn_hash,
                        "used_aggregator": True,
                        "route": panora_quote["route"],
                        "price_impact": panora_quote["price_impact"],
                        "output_amount": panora_quote["to_amount"],
                        "dex_breakdown": panora_quote.get("dex_breakdown", [])
                    }
                else:
                    logger.warning(f"⚠️  Panora unavailable: {panora_quote.get('error')}, using direct DEX")
            
            # Fallback to direct DEX swap
            current_price = await self.get_pair_price(quote_coin, base_coin, dex)
            min_output = int(quote_amount / current_price * (1 - slippage))
            
            txn_hash = await self.swap_exact_input(
                from_coin=quote_coin,
                to_coin=base_coin,
                amount_in=quote_amount,
                min_amount_out=min_output,
                dex=dex
            )
            
            return {
                "success": True,
                "txn_hash": txn_hash,
                "used_aggregator": False,
                "dex": dex or self.preferred_dex
            }
            
        except Exception as e:
            logger.error(f"Market buy failed: {e}")
            raise
    
    async def market_sell(
        self,
        base_coin: str,
        quote_coin: str,
        base_amount: int,
        slippage: float = None,
        dex: str = None,
        use_aggregator: bool = True
    ) -> Dict:
        """
        Execute market sell order
        If use_aggregator=True and Panora is enabled, uses aggregator for best price routing
        Returns: Dict with txn_hash and routing info
        """
        try:
            slippage = slippage or self.DEFAULT_SLIPPAGE
            
            # Try Panora aggregator first if enabled
            if use_aggregator and self.panora_enabled:
                logger.info("🎯 Using Panora Aggregator for best price routing...")
                panora_quote = await self._get_panora_quote(base_coin, quote_coin, base_amount, slippage)
                
                if panora_quote.get("success"):
                    logger.info(f"✅ Panora route: {' → '.join(panora_quote.get('route', []))} | Impact: {panora_quote.get('price_impact', 0)}%")
                    
                    # Use Panora's calculated output
                    min_output = panora_quote["to_amount"]
                    
                    # Execute swap on best DEX from route
                    if panora_quote.get("route"):
                        best_dex = panora_quote["route"][0].lower()
                        dex = best_dex if best_dex in ["pancakeswap", "thala", "liquidswap", "hyperion"] else dex
                    
                    txn_hash = await self.swap_exact_input(
                        from_coin=base_coin,
                        to_coin=quote_coin,
                        amount_in=base_amount,
                        min_amount_out=min_output,
                        dex=dex
                    )
                    
                    return {
                        "success": True,
                        "txn_hash": txn_hash,
                        "used_aggregator": True,
                        "route": panora_quote["route"],
                        "price_impact": panora_quote["price_impact"],
                        "output_amount": panora_quote["to_amount"],
                        "dex_breakdown": panora_quote.get("dex_breakdown", [])
                    }
                else:
                    logger.warning(f"⚠️  Panora unavailable: {panora_quote.get('error')}, using direct DEX")
            
            # Fallback to direct DEX swap
            current_price = await self.get_pair_price(base_coin, quote_coin, dex)
            min_output = int(base_amount * current_price * (1 - slippage))
            
            txn_hash = await self.swap_exact_input(
                from_coin=base_coin,
                to_coin=quote_coin,
                amount_in=base_amount,
                min_amount_out=min_output,
                dex=dex
            )
            
            return {
                "success": True,
                "txn_hash": txn_hash,
                "used_aggregator": False,
                "dex": dex or self.preferred_dex
            }
            
        except Exception as e:
            logger.error(f"Market sell failed: {e}")
            raise
    
    def format_amount(self, amount: int, decimals: int = 8) -> str:
        """Format amount from smallest unit to human readable"""
        return f"{amount / (10 ** decimals):.{decimals}f}"
    
    def parse_amount(self, amount: float, decimals: int = 8) -> int:
        """Parse human readable amount to smallest unit"""
        return int(amount * (10 ** decimals))
    
    async def get_transaction_history(self, limit: int = 100) -> List[Dict]:
        """Get transaction history for the account"""
        try:
            transactions = await self.client.account_transactions(
                str(self.account.address()),
                limit=limit
            )
            return transactions
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return []
    
    async def close(self):
        """Clean up resources"""
        if hasattr(self.info, 'close'):
            await self.info.close()
        logger.info("Aptos Exchange closed")

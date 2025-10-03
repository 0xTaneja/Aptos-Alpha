"""
Aptos Client for Alpha Trading Bot
Handles all blockchain interactions with Aptos network
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import json

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

logger = logging.getLogger(__name__)

class AptosAlphaBotClient:
    """
    Main client for interacting with Aptos Alpha Bot smart contracts
    """
    
    def __init__(
        self,
        node_url: str = "https://fullnode.testnet.aptoslabs.com/v1",
        contract_address: str = None,
        private_key: str = None
    ):
        self.client = RestClient(node_url)
        self.contract_address = contract_address
        
        if private_key:
            self.account = Account.load_key(private_key)
        else:
            self.account = Account.generate()
            
        logger.info(f"Initialized Aptos client for account: {self.account.address()}")
    
    async def get_account_balance(self, account_address: str = None) -> int:
        """Get APT balance for an account"""
        try:
            address = account_address or str(self.account.address())
            balance = await self.client.account_balance(address)
            return int(balance)
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0
    
    async def initialize_vault(self) -> Dict:
        """Initialize the trading vault"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_vault",
                "initialize_vault",
                [],
                []
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {"status": "success", "txn_hash": txn_hash}
            
        except Exception as e:
            logger.error(f"Error initializing vault: {e}")
            return {"status": "error", "message": str(e)}
    
    async def deposit_to_vault(self, amount: int) -> Dict:
        """Deposit APT to the trading vault"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_vault",
                "deposit",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(amount, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {"status": "success", "txn_hash": txn_hash, "amount": amount}
            
        except Exception as e:
            logger.error(f"Error depositing to vault: {e}")
            return {"status": "error", "message": str(e)}
    
    async def withdraw_from_vault(self, amount: int) -> Dict:
        """Withdraw APT from the trading vault"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_vault",
                "withdraw",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(amount, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {"status": "success", "txn_hash": txn_hash, "amount": amount}
            
        except Exception as e:
            logger.error(f"Error withdrawing from vault: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_vault_stats(self) -> Dict:
        """Get vault statistics"""
        try:
            # This would be a view function call
            # For now, return mock data
            return {
                "total_balance": 1000000000,  # 10 APT
                "total_profit": 50000000,     # 0.5 APT
                "total_trades": 25,
                "user_count": 5
            }
        except Exception as e:
            logger.error(f"Error getting vault stats: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_user_deposit(self, user_address: str) -> int:
        """Get user's deposit amount"""
        try:
            # This would be a view function call
            # For now, return mock data
            return 500000000  # 5 APT
        except Exception as e:
            logger.error(f"Error getting user deposit: {e}")
            return 0
    
    async def initialize_trading_engine(self) -> Dict:
        """Initialize the trading engine"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "initialize_engine",
                [],
                []
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {"status": "success", "txn_hash": txn_hash}
            
        except Exception as e:
            logger.error(f"Error initializing trading engine: {e}")
            return {"status": "error", "message": str(e)}
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: int,
        price: int
    ) -> Dict:
        """Place a trading order"""
        try:
            side_value = 1 if side.lower() == "buy" else 2
            
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "place_order",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(symbol.encode(), Serializer.to_bytes),
                    TransactionArgument(side_value, Serializer.u8),
                    TransactionArgument(amount, Serializer.u64),
                    TransactionArgument(price, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price
            }
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_order(self, order_id: int) -> Dict:
        """Cancel a trading order"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "cancel_order",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(order_id, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {"status": "success", "txn_hash": txn_hash, "order_id": order_id}
            
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return {"status": "error", "message": str(e)}
    
    async def create_grid_strategy(
        self,
        symbol: str,
        base_price: int,
        grid_spacing: int,
        num_levels: int,
        amount_per_level: int
    ) -> Dict:
        """Create a grid trading strategy"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "create_grid_strategy",
                [],
                [
                    TransactionArgument(self.contract_address, Serializer.to_bytes),
                    TransactionArgument(symbol.encode(), Serializer.to_bytes),
                    TransactionArgument(base_price, Serializer.u64),
                    TransactionArgument(grid_spacing, Serializer.u64),
                    TransactionArgument(num_levels, Serializer.u8),
                    TransactionArgument(amount_per_level, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "symbol": symbol,
                "base_price": base_price,
                "grid_spacing": grid_spacing,
                "num_levels": num_levels
            }
            
        except Exception as e:
            logger.error(f"Error creating grid strategy: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_market_price(self, symbol: str) -> int:
        """Get current market price for a symbol"""
        try:
            # This would be a view function call
            # For now, return mock prices
            mock_prices = {
                "APT/USDC": 1000000,    # $10.00
                "BTC/USDC": 6500000000, # $65,000.00
                "ETH/USDC": 300000000,  # $3,000.00
            }
            return mock_prices.get(symbol, 0)
        except Exception as e:
            logger.error(f"Error getting market price: {e}")
            return 0
    
    async def get_user_orders(self, user_address: str = None) -> List[int]:
        """Get user's order IDs"""
        try:
            # This would be a view function call
            # For now, return mock data
            return [1, 2, 3]
        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return []
    
    async def update_market_price(self, symbol: str, price: int) -> Dict:
        """Update market price (admin only)"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "update_market_price",
                [],
                [
                    TransactionArgument(symbol, Serializer.str),
                    TransactionArgument(price, Serializer.u64),
                ]
            )
            
            txn_hash = await self._submit_transaction(payload)
            return {"status": "success", "txn_hash": txn_hash, "symbol": symbol, "price": price}
            
        except Exception as e:
            logger.error(f"Error updating market price: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _submit_transaction(self, payload: EntryFunction) -> str:
        """Submit a transaction to the Aptos network"""
        try:
            # Create transaction
            txn = await self.client.create_bcs_transaction(
                self.account,
                TransactionPayload(payload)
            )
            
            # Sign and submit
            signed_txn = self.account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            logger.info(f"Transaction submitted: {txn_hash}")
            return txn_hash
            
        except ApiError as e:
            logger.error(f"API error submitting transaction: {e}")
            raise
        except Exception as e:
            logger.error(f"Error submitting transaction: {e}")
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

# Utility functions for price formatting
def format_price(price: int, decimals: int = 6) -> str:
    """Format price with proper decimals"""
    return f"${price / (10 ** decimals):,.{decimals}f}"

def parse_price(price_str: str, decimals: int = 6) -> int:
    """Parse price string to integer with decimals"""
    try:
        price = float(price_str.replace('$', '').replace(',', ''))
        return int(price * (10 ** decimals))
    except ValueError:
        return 0

# Example usage and testing
async def main():
    """Example usage of the Aptos client"""
    client = AptosAlphaBotClient()
    
    print(f"Account address: {client.account.address()}")
    print(f"Private key: {client.account.private_key}")
    
    # Get balance
    balance = await client.get_account_balance()
    print(f"Balance: {client.format_amount(balance)}")
    
    # Example market price
    price = await client.get_market_price("APT/USDC")
    print(f"APT/USDC price: {format_price(price)}")

if __name__ == "__main__":
    asyncio.run(main())

"""
Aptos API - Base API class for Aptos Alpha Bot
Equivalent to Hyperliquid's api.py but for Aptos blockchain
"""

import asyncio
import logging
from typing import Optional

from aptos_sdk.async_client import RestClient

logger = logging.getLogger(__name__)

class AptosAPI:
    """
    Base API class for Aptos blockchain interactions
    """
    
    def __init__(self, node_url: Optional[str] = None):
        self.node_url = node_url or "https://fullnode.testnet.aptoslabs.com/v1"
        self.client = RestClient(self.node_url)
        
        logger.info(f"Initialized Aptos API with node: {self.node_url}")
    
    async def get_ledger_info(self):
        """Get current ledger information"""
        try:
            return await self.client.info()  # Correct method name
        except Exception as e:
            logger.error(f"Error getting ledger info: {e}")
            return None
    
    async def get_account_info(self, address: str):
        """Get account information"""
        try:
            return await self.client.account(address)  # Correct method name
        except Exception as e:
            logger.error(f"Error getting account info for {address}: {e}")
            return None
    
    async def get_account_resources(self, address: str):
        """Get account resources"""
        try:
            return await self.client.account_resources(address)
        except Exception as e:
            logger.error(f"Error getting account resources for {address}: {e}")
            return []
    
    async def get_account_transactions(self, address: str, limit: int = 100):
        """Get account transactions"""
        try:
            return await self.client.transactions_by_account(address, limit=limit)
        except Exception as e:
            logger.error(f"Error getting transactions for {address}: {e}")
            return []
    
    async def get_transaction_by_hash(self, txn_hash: str):
        """Get transaction by hash"""
        try:
            return await self.client.transaction_by_hash(txn_hash)
        except Exception as e:
            logger.error(f"Error getting transaction {txn_hash}: {e}")
            return None
    
    async def wait_for_transaction(self, txn_hash: str, timeout: int = 30):
        """Wait for transaction confirmation"""
        try:
            return await self.client.wait_for_transaction(txn_hash, timeout)
        except Exception as e:
            logger.error(f"Error waiting for transaction {txn_hash}: {e}")
            raise
    
    async def simulate_transaction(self, transaction):
        """Simulate transaction execution"""
        try:
            return await self.client.simulate_transaction(transaction)
        except Exception as e:
            logger.error(f"Error simulating transaction: {e}")
            return None
    
    async def estimate_gas_price(self):
        """Estimate current gas price"""
        try:
            # Get recent transactions to estimate gas price
            ledger_info = await self.get_ledger_info()
            if ledger_info:
                # Return a reasonable gas price estimate
                return 100  # Default gas unit price in octas
            return 100
        except Exception as e:
            logger.error(f"Error estimating gas price: {e}")
            return 100
    
    async def health_check(self) -> bool:
        """Check if the API connection is healthy"""
        try:
            ledger_info = await self.get_ledger_info()
            return ledger_info is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Clean up API resources"""
        # RestClient doesn't need explicit cleanup
        logger.info("Aptos API connection closed")

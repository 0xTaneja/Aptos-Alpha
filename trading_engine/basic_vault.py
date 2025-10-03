"""
Aptos Vault Operations
Demonstrates vault management and trading operations on Aptos
"""

import asyncio
import logging
from typing import Dict, Optional
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

logger = logging.getLogger(__name__)

class AptosVaultManager:
    """Manages vault operations on Aptos"""
    
    def __init__(self, client: RestClient, account: Account, vault_address: str = None):
        self.client = client
        self.account = account
        self.vault_address = vault_address or "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.contract_address = "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.logger = logging.getLogger(__name__)
        
    async def place_vault_order(self, token_address: str, is_buy: bool, amount: float, price: float) -> Dict:
        """Place an order using vault funds"""
        try:
            amount_units = int(amount * 100000000)
            price_units = int(price * 100000000)
            
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "place_vault_order",
                [],
                [
                    TransactionArgument(self.vault_address, Serializer.str),
                    TransactionArgument(token_address, Serializer.str),
                    TransactionArgument(is_buy, Serializer.bool),
                    TransactionArgument(amount_units, Serializer.u64),
                    TransactionArgument(price_units, Serializer.u64),
                ]
            )
            
            txn = await self.client.create_bcs_transaction(self.account, TransactionPayload(payload))
            signed_txn = self.account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            await self.client.wait_for_transaction(txn_hash)
            
            return {"status": "success", "txn_hash": txn_hash}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def cancel_vault_order(self, order_id: str) -> Dict:
        """Cancel a vault order"""
        try:
            payload = EntryFunction.natural(
                f"{self.contract_address}::trading_engine",
                "cancel_vault_order",
                [],
                [
                    TransactionArgument(self.vault_address, Serializer.str),
                    TransactionArgument(order_id, Serializer.str),
                ]
            )
            
            txn = await self.client.create_bcs_transaction(self.account, TransactionPayload(payload))
            signed_txn = self.account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            await self.client.wait_for_transaction(txn_hash)
            
            return {"status": "success", "txn_hash": txn_hash}
        except Exception as e:
            return {"status": "error", "message": str(e)}

async def main():
    """Example usage of Aptos Vault Manager"""
    client = RestClient("https://fullnode.testnet.aptoslabs.com/v1")
    account = Account.generate()
    
    vault_manager = AptosVaultManager(client, account)
    
    try:
        # Place an APT order with low price to ensure it rests
        print("Placing APT buy order...")
        order_result = await vault_manager.place_vault_order(
            token_address="0x1::aptos_coin::AptosCoin",
            is_buy=True,
            amount=0.2,
            price=8.5  # Low price
        )
        print(f"Order result: {order_result}")
        
        # Cancel the order if successful
        if order_result["status"] == "success":
            print("Cancelling order...")
            cancel_result = await vault_manager.cancel_vault_order("order_1")
            print(f"Cancel result: {cancel_result}")
        
        print("Aptos vault operations completed")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

"""
Aptos Event Streaming
Real-time event monitoring and subscription system for Aptos blockchain
"""

import asyncio
import logging
from typing import Callable
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account

logger = logging.getLogger(__name__)

class AptosEventStreamer:
    """Real-time event streaming for Aptos blockchain"""
    
    def __init__(self, client: RestClient, account: Account):
        self.client = client
        self.account = account
        self.running = False
        
    async def subscribe_to_token_prices(self, callback: Callable):
        """Subscribe to real-time token price updates"""
        while self.running:
            try:
                # Get APT price
                import requests
                response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=aptos&vs_currencies=usd")
                if response.status_code == 200:
                    data = response.json()
                    price_data = {"type": "price_update", "token": "APT", "price": data.get("aptos", {}).get("usd", 10.0)}
                    callback(price_data)
            except Exception as e:
                logger.error(f"Error getting price: {e}")
            await asyncio.sleep(5)
    
    async def subscribe_to_user_events(self, user_address: str, callback: Callable):
        """Subscribe to user-specific events"""
        last_sequence = 0
        while self.running:
            try:
                account_txns = await self.client.account_transactions(user_address, limit=5)
                for txn in account_txns:
                    sequence_number = int(txn.get("sequence_number", 0))
                    if sequence_number > last_sequence:
                        event_data = {
                            "type": "user_transaction",
                            "user": user_address,
                            "hash": txn.get("hash"),
                            "success": txn.get("success", False)
                        }
                        callback(event_data)
                        last_sequence = max(last_sequence, sequence_number)
            except Exception as e:
                logger.error(f"Error monitoring user events: {e}")
            await asyncio.sleep(2)
    
    async def start_streaming(self):
        """Start the event streaming"""
        self.running = True
        logger.info("Aptos event streaming started")

async def main():
    """Example usage of Aptos Event Streamer"""
    client = RestClient("https://fullnode.testnet.aptoslabs.com/v1")
    account = Account.generate()
    address = str(account.address())
    
    streamer = AptosEventStreamer(client, account)
    
    # Start streaming
    await streamer.start_streaming()
    
    # Subscribe to events
    price_task = asyncio.create_task(streamer.subscribe_to_token_prices(lambda data: print(f"Price: {data}")))
    user_task = asyncio.create_task(streamer.subscribe_to_user_events(address, lambda data: print(f"User Event: {data}")))
    
    print("Aptos event streaming active. Press Ctrl+C to stop")
    
    try:
        await asyncio.gather(price_task, user_task)
    except KeyboardInterrupt:
        streamer.running = False
        print("Event streaming stopped")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

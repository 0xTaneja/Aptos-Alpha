"""
Aptos Order Scheduling and Cancellation
Demonstrates order placement with scheduled cancellation on Aptos
"""

import asyncio
import time
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

class AptosOrderScheduler:
    """
    Handles order scheduling and cancellation on Aptos
    Provides functionality to place orders and schedule their cancellation
    """
    
    def __init__(self, client: RestClient, account: Account, contract_address: str = None):
        self.client = client
        self.account = account
        self.contract_address = contract_address or "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.logger = logging.getLogger(__name__)
        self.scheduled_tasks = {}  # {order_id: asyncio.Task}
        
    async def place_order_with_schedule(self, token_address: str, is_buy: bool, 
                                       amount: float, price: float, 
                                       cancel_after_seconds: int = None) -> Dict:
        """
        Place an order on Aptos with optional scheduled cancellation
        
        Args:
            token_address: Token contract address
            is_buy: True for buy, False for sell
            amount: Order amount
            price: Order price
            cancel_after_seconds: Seconds after which to cancel the order
        """
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
                self.account,
                TransactionPayload(payload)
            )
            
            signed_txn = self.account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            # Get order ID from transaction result
            order_id = await self._extract_order_id_from_transaction(txn_hash)
            
            self.logger.info(f"Order placed successfully: {order_id}")
            
            # Schedule cancellation if requested
            if cancel_after_seconds and order_id:
                cancel_task = asyncio.create_task(
                    self._schedule_cancel(order_id, cancel_after_seconds)
                )
                self.scheduled_tasks[order_id] = cancel_task
                self.logger.info(f"Order {order_id} scheduled for cancellation in {cancel_after_seconds} seconds")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "order_id": order_id,
                "token": token_address,
                "is_buy": is_buy,
                "amount": amount,
                "price": price,
                "scheduled_cancel": cancel_after_seconds is not None
            }
            
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _extract_order_id_from_transaction(self, txn_hash: str) -> Optional[str]:
        """Extract order ID from transaction events"""
        try:
            # Get transaction details
            txn_info = await self.client.transaction_by_hash(txn_hash)
            
            # Look for order placement events
            if "events" in txn_info:
                for event in txn_info["events"]:
                    if "OrderPlaced" in event.get("type", ""):
                        return event.get("data", {}).get("order_id")
            
            # Fallback: generate order ID from transaction hash
            return f"order_{txn_hash[:16]}"
            
        except Exception as e:
            self.logger.error(f"Error extracting order ID: {e}")
            return f"order_{int(time.time())}"
    
    async def _schedule_cancel(self, order_id: str, delay_seconds: int):
        """Schedule order cancellation after delay"""
        try:
            # Wait for the specified delay
            await asyncio.sleep(delay_seconds)
            
            # Cancel the order
            result = await self.cancel_order(order_id)
            
            if result["status"] == "success":
                self.logger.info(f"Scheduled cancellation completed for order {order_id}")
            else:
                self.logger.error(f"Scheduled cancellation failed for order {order_id}: {result.get('message')}")
            
            # Remove from scheduled tasks
            if order_id in self.scheduled_tasks:
                del self.scheduled_tasks[order_id]
                
        except asyncio.CancelledError:
            self.logger.info(f"Scheduled cancellation cancelled for order {order_id}")
        except Exception as e:
            self.logger.error(f"Error in scheduled cancellation for order {order_id}: {e}")
    
    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel a specific order on Aptos"""
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
                self.account,
                TransactionPayload(payload)
            )
            
            signed_txn = self.account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            self.logger.info(f"Order cancelled successfully: {order_id}")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "order_id": order_id
            }
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def query_order_status(self, order_id: str) -> Dict:
        """Query the status of an order from Aptos blockchain"""
        try:
            # Query order status from trading contract
            address = str(self.account.address())
            resources = await self.client.account_resources(address)
            
            # Look for UserOrders resource
            for resource in resources:
                if "UserOrders" in resource["type"]:
                    orders_data = resource["data"]
                    orders = orders_data.get("orders", [])
                    
                    for order in orders:
                        if order.get("id") == order_id:
                            return {
                                "status": "found",
                                "order": order
                            }
            
            # Order not found in active orders
            return {
                "status": "not_found",
                "message": f"Order {order_id} not found in active orders"
            }
            
        except Exception as e:
            self.logger.error(f"Error querying order status for {order_id}: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_open_orders(self) -> Dict:
        """Get all open orders for the account"""
        try:
            address = str(self.account.address())
            resources = await self.client.account_resources(address)
            
            # Look for UserOrders resource
            for resource in resources:
                if "UserOrders" in resource["type"]:
                    orders_data = resource["data"]
                    orders = orders_data.get("orders", [])
                    
                    # Filter for open orders
                    open_orders = [
                        order for order in orders 
                        if order.get("status") in ["pending", "partially_filled"]
                    ]
                    
                    return {
                        "status": "success",
                        "orders": open_orders,
                        "count": len(open_orders)
                    }
            
            # No orders resource found
            return {
                "status": "success",
                "orders": [],
                "count": 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return {"status": "error", "message": str(e)}
    
    def cancel_scheduled_cancellation(self, order_id: str) -> bool:
        """Cancel a scheduled cancellation"""
        if order_id in self.scheduled_tasks:
            task = self.scheduled_tasks[order_id]
            if not task.done():
                task.cancel()
            del self.scheduled_tasks[order_id]
            self.logger.info(f"Cancelled scheduled cancellation for order {order_id}")
            return True
        return False
    
    async def cleanup(self):
        """Clean up all scheduled tasks"""
        for order_id, task in self.scheduled_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.scheduled_tasks.clear()
        self.logger.info("Order scheduler cleanup completed")

async def main():
    """
    Example usage of Aptos Order Scheduler
    Demonstrates placing orders with scheduled cancellation
    """
    # Initialize Aptos client and account
    client = RestClient("https://fullnode.testnet.aptoslabs.com/v1")
    
    # For demo purposes - in production, load from secure storage
    account = Account.generate()
    
    # Initialize order scheduler
    scheduler = AptosOrderScheduler(client, account)
    
    try:
        # Place an order with scheduled cancellation
        print("Placing APT buy order with 10-second cancellation...")
        order_result = await scheduler.place_order_with_schedule(
            token_address="0x1::aptos_coin::AptosCoin",
            is_buy=True,
            amount=0.2,
            price=8.5,  # Low price to ensure it rests
            cancel_after_seconds=10
        )
        print(f"Order result: {order_result}")
        
        if order_result["status"] == "success":
            order_id = order_result["order_id"]
            
            # Query order status
            print(f"\nQuerying order status for {order_id}...")
            status_result = await scheduler.query_order_status(order_id)
            print(f"Order status: {status_result}")
            
            # Wait for scheduled cancellation
            print("\nWaiting for scheduled cancellation...")
            await asyncio.sleep(12)
            
            # Check open orders after cancellation
            print("\nChecking open orders after cancellation...")
            open_orders = await scheduler.get_open_orders()
            print(f"Open orders: {open_orders}")
        
        # Clean up
        await scheduler.cleanup()
        print("\nAptos order scheduling completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Run the example
    asyncio.run(main())
"""
Cancel Open Orders on Aptos
Utility to cancel all open orders for an account on Aptos
"""

import asyncio
import logging
from typing import Dict, List
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

logger = logging.getLogger(__name__)

class AptosOrderCanceller:
    """
    Utility class to cancel open orders on Aptos
    """
    
    def __init__(self, client: RestClient, account: Account, contract_address: str = None):
        self.client = client
        self.account = account
        self.contract_address = contract_address or "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.logger = logging.getLogger(__name__)
        
    async def get_open_orders(self) -> List[Dict]:
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
                        if order.get("status") in ["pending", "partially_filled", "active"]
                    ]
                    
                    return open_orders
            
            # No orders resource found
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return []
    
    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel a specific order"""
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
            return {"status": "error", "message": str(e), "order_id": order_id}
    
    async def cancel_all_orders(self) -> Dict:
        """Cancel all open orders for the account"""
        try:
            # Get all open orders
            open_orders = await self.get_open_orders()
            
            if not open_orders:
                self.logger.info("No open orders found to cancel")
                return {
                    "status": "success",
                    "message": "No open orders found",
                    "cancelled_count": 0,
                    "failed_count": 0
                }
            
            self.logger.info(f"Found {len(open_orders)} open orders to cancel")
            
            # Cancel each order
            cancelled_count = 0
            failed_count = 0
            results = []
            
            for order in open_orders:
                order_id = order.get("id") or order.get("order_id")
                token = order.get("token") or order.get("coin", "Unknown")
                
                print(f"Cancelling order {order_id} for {token}...")
                
                result = await self.cancel_order(order_id)
                results.append(result)
                
                if result["status"] == "success":
                    cancelled_count += 1
                    print(f"✅ Successfully cancelled order {order_id}")
                else:
                    failed_count += 1
                    print(f"❌ Failed to cancel order {order_id}: {result.get('message')}")
                
                # Small delay between cancellations to avoid rate limiting
                await asyncio.sleep(0.5)
            
            summary = {
                "status": "completed",
                "total_orders": len(open_orders),
                "cancelled_count": cancelled_count,
                "failed_count": failed_count,
                "results": results
            }
            
            self.logger.info(f"Order cancellation completed: {cancelled_count} cancelled, {failed_count} failed")
            return summary
            
        except Exception as e:
            self.logger.error(f"Error cancelling all orders: {e}")
            return {"status": "error", "message": str(e)}
    
    async def cancel_orders_by_token(self, token_address: str) -> Dict:
        """Cancel all orders for a specific token"""
        try:
            # Get all open orders
            open_orders = await self.get_open_orders()
            
            # Filter orders for the specific token
            token_orders = [
                order for order in open_orders 
                if order.get("token") == token_address or order.get("coin") == token_address
            ]
            
            if not token_orders:
                self.logger.info(f"No open orders found for token {token_address}")
                return {
                    "status": "success",
                    "message": f"No open orders found for token {token_address}",
                    "cancelled_count": 0,
                    "failed_count": 0
                }
            
            self.logger.info(f"Found {len(token_orders)} open orders for {token_address}")
            
            # Cancel each order for this token
            cancelled_count = 0
            failed_count = 0
            results = []
            
            for order in token_orders:
                order_id = order.get("id") or order.get("order_id")
                
                print(f"Cancelling order {order_id} for {token_address}...")
                
                result = await self.cancel_order(order_id)
                results.append(result)
                
                if result["status"] == "success":
                    cancelled_count += 1
                    print(f"✅ Successfully cancelled order {order_id}")
                else:
                    failed_count += 1
                    print(f"❌ Failed to cancel order {order_id}: {result.get('message')}")
                
                await asyncio.sleep(0.5)
            
            summary = {
                "status": "completed",
                "token": token_address,
                "total_orders": len(token_orders),
                "cancelled_count": cancelled_count,
                "failed_count": failed_count,
                "results": results
            }
            
            self.logger.info(f"Token order cancellation completed: {cancelled_count} cancelled, {failed_count} failed")
            return summary
            
        except Exception as e:
            self.logger.error(f"Error cancelling orders for token {token_address}: {e}")
            return {"status": "error", "message": str(e)}

async def main():
    """
    Example usage of Aptos Order Canceller
    Cancels all open orders for the account
    """
    # Initialize Aptos client and account
    client = RestClient("https://fullnode.testnet.aptoslabs.com/v1")
    
    # For demo purposes - in production, load from secure storage
    account = Account.generate()
    address = str(account.address())
    
    # Initialize order canceller
    canceller = AptosOrderCanceller(client, account)
    
    try:
        print(f"Checking open orders for account: {address}")
        
        # Get open orders first
        open_orders = await canceller.get_open_orders()
        print(f"Found {len(open_orders)} open orders")
        
        if open_orders:
            # Display orders
            for i, order in enumerate(open_orders, 1):
                order_id = order.get("id", "Unknown")
                token = order.get("token", "Unknown")
                side = order.get("side", "Unknown")
                amount = order.get("amount", "Unknown")
                price = order.get("price", "Unknown")
                status = order.get("status", "Unknown")
                
                print(f"{i}. Order {order_id}: {side} {amount} {token} @ {price} ({status})")
            
            # Cancel all orders
            print("\nCancelling all open orders...")
            result = await canceller.cancel_all_orders()
            
            print(f"\nCancellation Summary:")
            print(f"Total orders: {result.get('total_orders', 0)}")
            print(f"Successfully cancelled: {result.get('cancelled_count', 0)}")
            print(f"Failed to cancel: {result.get('failed_count', 0)}")
            
        else:
            print("No open orders found to cancel")
        
        print("\nAptos order cancellation completed")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the cancellation
    asyncio.run(main())

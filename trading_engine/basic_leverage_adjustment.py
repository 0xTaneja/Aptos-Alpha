"""
Basic Position Management for Aptos Trading Bot
Handles position sizing, risk management, and portfolio adjustments
"""

import json
import asyncio
import logging
from typing import Dict, Optional, List
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

logger = logging.getLogger(__name__)

class AptosPositionManager:
    """
    Manages positions and risk for Aptos trading operations
    Replaces leverage-based concepts with position sizing and risk management
    """
    
    def __init__(self, client: RestClient, account: Account, contract_address: str = None):
        self.client = client
        self.account = account
        self.contract_address = contract_address or "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.logger = logging.getLogger(__name__)
        
    async def get_user_positions(self) -> Dict:
        """Get current user positions across all tokens"""
        try:
            address = str(self.account.address())
            
            # Query user positions from trading contract
            try:
                resources = await self.client.account_resources(address)
                positions = {}
                
                for resource in resources:
                    if "UserPositions" in resource["type"]:
                        positions_data = resource["data"]
                        return positions_data
                        
                    # Also check for individual token balances
                    if "CoinStore" in resource["type"]:
                        # Extract token type from resource type
                        type_parts = resource["type"].split("<")
                        if len(type_parts) > 1:
                            token_type = type_parts[1].split(">")[0]
                            coin_data = resource["data"]["coin"]
                            balance = int(coin_data["value"])
                            
                            if balance > 0:
                                token_symbol = token_type.split("::")[-1]
                                positions[token_symbol] = {
                                    "balance": balance,
                                    "balance_formatted": balance / 100000000,
                                    "token_type": token_type
                                }
                
                return positions
                
            except Exception as e:
                self.logger.error(f"Error querying positions from contract: {e}")
                
                # Fallback: get basic APT balance
                apt_balance = await self.client.account_balance(address)
                return {
                    "APT": {
                        "balance": apt_balance,
                        "balance_formatted": apt_balance / 100000000,
                        "token_type": "0x1::aptos_coin::AptosCoin"
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting user positions: {e}")
            return {}

async def main():
    """
    Example usage of Aptos Position Manager
    Demonstrates position management and risk adjustment
    """
    # Initialize Aptos client and account
    client = RestClient("https://fullnode.testnet.aptoslabs.com/v1")
    
    # For demo purposes - in production, load from secure storage
    account = Account.generate()
    
    # Initialize position manager
    position_manager = AptosPositionManager(client, account)
    
    try:
        # Get current positions
        print("Getting current positions...")
        positions = await position_manager.get_user_positions()
        print("Current positions:", json.dumps(positions, indent=2))
        
        print("Aptos position management completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the example
    asyncio.run(main())

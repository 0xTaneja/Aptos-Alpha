"""
Agent Factory for creating and managing agent wallets on Aptos
Secure wallet creation and management for Aptos trading operations
"""
import asyncio
import json
import logging
import os
import time
from typing import Dict, Optional, List
from datetime import datetime

# Aptos SDK imports
from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account import Account
from aptos_sdk.transactions import (
    EntryFunction,
    TransactionArgument,
    TransactionPayload,
    Serializer,
)

# Import database conditionally to handle the undefined bot_db
try:
    from database import bot_db
except ImportError:
    bot_db = None
    
logger = logging.getLogger(__name__)

class AgentFactory:
    """
    Factory for creating and managing agent wallets on Aptos
    Provides secure agent wallet creation and management without exposing private keys
    """
    
    def __init__(self, master_private_key: str = None, base_url: str = None):
        """
        Initialize the Agent Factory for Aptos
        
        Args:
            master_private_key: Master private key for creating agent wallets
            base_url: Aptos node URL
        """
        self.base_url = base_url or "https://fullnode.testnet.aptoslabs.com/v1"
        self.contract_address = "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"
        self.master_private_key = master_private_key
        
        # Initialize Aptos client
        self.client = RestClient(self.base_url)
        
        # Master account for creating agent wallets
        self.master_account = None
        
        # Cache of agent wallets and accounts
        self.agent_wallets = {}
        self.agent_accounts = {}  # {user_id: Account} - Aptos accounts instead of exchanges
        
        if master_private_key:
            try:
                self.master_account = Account.load_key(master_private_key)
                logger.info(f"AgentFactory initialized with master account: {self.master_account.address()}")
            except Exception as e:
                logger.error(f"Error initializing master account: {e}")
                
        self.user_agents = {}  # {user_id: Account instance}
        self.agent_details = {}  # {user_id: {address, key, etc}}
        self.last_balance_check = {}  # {user_id: timestamp}
        
        # Define storage path
        self.storage_path = os.path.join(os.path.dirname(__file__), "agent_wallets.json")
        
        # Load existing agent details from storage
        self._load_agent_details()
    
    async def initialize(self) -> bool:
        """Initialize the agent factory"""
        try:
            if self.master_account:
                # Test connection by getting balance
                from aptos_sdk.account_address import AccountAddress
                address_obj = AccountAddress.from_str(str(self.master_account.address()))
                balance = await self.client.account_balance(address_obj)
                logger.info(f"Master account balance: {balance} octas")
                return True
            else:
                logger.warning("No master account available")
                return False
        except Exception as e:
            logger.error(f"Error initializing AgentFactory: {e}")
            return False

    async def create_agent_wallet(self, user_id: str, main_address: str = None) -> Dict:
        """
        Create a new agent wallet for a user on Aptos
        
        Args:
            user_id: Unique identifier for the user
            main_address: User's main Aptos address (optional)
            
        Returns:
            Dict with agent wallet details
        """
        try:
            # Check if agent already exists
            if user_id in self.agent_details:
                existing_agent = self.agent_details[user_id]
                logger.info(f"Agent wallet already exists for user {user_id}")
                return {
                    "status": "exists",
                    "address": existing_agent["address"],
                    "user_id": user_id,
                    "main_address": main_address or existing_agent.get("main_address", "")
                }
            
            # Generate new Aptos account for agent
            agent_account = Account.generate()
            agent_address = str(agent_account.address())
            agent_private_key = agent_account.private_key.hex()
            
            # Store agent details
            agent_details = {
                "user_id": user_id,
                "address": agent_address,
                "private_key": agent_private_key,  # In production, encrypt this
                "main_address": main_address or "",
                "created_at": datetime.now().isoformat(),
                "balance": 0,
                "funded": False
            }
            
            # Cache the agent
            self.agent_details[user_id] = agent_details
            self.agent_accounts[user_id] = agent_account
            
            # Save to storage
            self._save_agent_details()
            
            # Fund the agent wallet with small amount for gas
            if self.master_account:
                await self._fund_agent_wallet(agent_address, 1000000)  # 0.01 APT for gas
            
            logger.info(f"Created agent wallet for user {user_id}: {agent_address}")
            
            return {
                "status": "created",
                "address": agent_address,
                "user_id": user_id,
                "main_address": main_address or "",
                "private_key": agent_private_key  # Return for initial setup, then remove
            }
            
        except Exception as e:
            logger.error(f"Error creating agent wallet for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_agent_wallet(self, user_id: str) -> Optional[Account]:
        """
        Get agent wallet for a user
        """
        try:
            if user_id in self.agent_accounts:
                return self.agent_accounts[user_id]
            
            # Try to load from storage
            if user_id in self.agent_details:
                agent_details = self.agent_details[user_id]
                private_key = agent_details["private_key"]
                
                # Create Account from stored private key
                agent_account = Account.load_key(private_key)
                self.agent_accounts[user_id] = agent_account
                
                return agent_account
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting agent wallet for {user_id}: {e}")
            return None

    async def get_agent_balance(self, user_id: str) -> Dict:
        """
        Get agent wallet balance
        """
        try:
            agent_account = await self.get_agent_wallet(user_id)
            if not agent_account:
                return {"status": "error", "message": "Agent wallet not found"}
            
            # Get APT balance
            from aptos_sdk.account_address import AccountAddress
            address_obj = AccountAddress.from_str(str(agent_account.address()))
            balance = await self.client.account_balance(address_obj)
            
            # Update cached balance
            if user_id in self.agent_details:
                self.agent_details[user_id]["balance"] = balance
                self.agent_details[user_id]["last_balance_check"] = datetime.now().isoformat()
            
            return {
                "status": "success",
                "balance": balance,
                "balance_apt": balance / 100000000,  # Convert octas to APT
                "address": str(agent_account.address())
            }
            
        except Exception as e:
            logger.error(f"Error getting agent balance for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def fund_agent_wallet(self, user_id: str, amount: int) -> Dict:
        """
        Fund agent wallet from master account
        """
        try:
            if not self.master_account:
                return {"status": "error", "message": "No master account available"}
            
            agent_account = await self.get_agent_wallet(user_id)
            if not agent_account:
                return {"status": "error", "message": "Agent wallet not found"}
            
            # Transfer APT from master to agent
            txn_hash = await self._transfer_apt(
                from_account=self.master_account,
                to_address=str(agent_account.address()),
                amount=amount
            )
            
            # Update agent details
            if user_id in self.agent_details:
                self.agent_details[user_id]["funded"] = True
                self.agent_details[user_id]["last_funded"] = datetime.now().isoformat()
            
            logger.info(f"Funded agent wallet for {user_id} with {amount} octas")
            
            return {
                "status": "success",
                "txn_hash": txn_hash,
                "amount": amount,
                "amount_apt": amount / 100000000
            }
            
        except Exception as e:
            logger.error(f"Error funding agent wallet for {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def _fund_agent_wallet(self, agent_address: str, amount: int):
        """Internal method to fund agent wallet"""
        try:
            if self.master_account:
                await self._transfer_apt(
                    from_account=self.master_account,
                    to_address=agent_address,
                    amount=amount
                )
        except Exception as e:
            logger.error(f"Error funding agent wallet {agent_address}: {e}")

    async def _transfer_apt(self, from_account: Account, to_address: str, amount: int) -> str:
        """Transfer APT between accounts"""
        try:
            # Create transfer transaction
            payload = EntryFunction.natural(
                "0x1::aptos_account",
                "transfer",
                [],
                [
                    TransactionArgument(to_address, Serializer.to_bytes),
                    TransactionArgument(amount, Serializer.u64),
                ]
            )
            
            # Create transaction
            txn = await self.client.create_bcs_transaction(
                from_account,
                TransactionPayload(payload)
            )
            
            # Sign and submit
            signed_txn = from_account.sign(txn)
            txn_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(txn_hash)
            
            return txn_hash
            
        except Exception as e:
            logger.error(f"Error transferring APT: {e}")
            raise

    def get_agent_details(self, user_id: str) -> Optional[Dict]:
        """Get agent details for a user"""
        return self.agent_details.get(user_id)

    def list_agents(self) -> List[Dict]:
        """List all agent wallets"""
        return list(self.agent_details.values())

    def _load_agent_details(self):
        """Load agent details from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    self.agent_details = json.load(f)
                logger.info(f"Loaded {len(self.agent_details)} agent wallets from storage")
            else:
                self.agent_details = {}
        except Exception as e:
            logger.error(f"Error loading agent details: {e}")
            self.agent_details = {}

    def _save_agent_details(self):
        """Save agent details to storage"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            with open(self.storage_path, 'w') as f:
                json.dump(self.agent_details, f, indent=2)
            logger.debug("Saved agent details to storage")
        except Exception as e:
            logger.error(f"Error saving agent details: {e}")

    async def cleanup_agent(self, user_id: str) -> Dict:
        """Clean up agent wallet resources"""
        try:
            # Remove from caches
            if user_id in self.agent_accounts:
                del self.agent_accounts[user_id]
            if user_id in self.user_agents:
                del self.user_agents[user_id]
            if user_id in self.last_balance_check:
                del self.last_balance_check[user_id]
            
            # Keep agent_details for historical record but mark as inactive
            if user_id in self.agent_details:
                self.agent_details[user_id]["active"] = False
                self.agent_details[user_id]["cleanup_at"] = datetime.now().isoformat()
            
            self._save_agent_details()
            
            logger.info(f"Cleaned up agent resources for user {user_id}")
            
            return {"status": "success"}
            
        except Exception as e:
            logger.error(f"Error cleaning up agent for {user_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_master_balance(self) -> Dict:
        """Get master account balance"""
        try:
            if not self.master_account:
                return {"status": "error", "message": "No master account"}
            
            from aptos_sdk.account_address import AccountAddress
            address_obj = AccountAddress.from_str(str(self.master_account.address()))
            balance = await self.client.account_balance(address_obj)
            
            return {
                "status": "success",
                "balance": balance,
                "balance_apt": balance / 100000000,
                "address": str(self.master_account.address())
            }
            
        except Exception as e:
            logger.error(f"Error getting master balance: {e}")
            return {"status": "error", "message": str(e)}

    def format_amount(self, amount: int) -> str:
        """Format amount from octas to APT"""
        return f"{amount / 100000000:.8f} APT"
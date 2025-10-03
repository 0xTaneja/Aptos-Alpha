"""
Aptos Network Connector for real blockchain interactions
Converted from HyperEVM network connector for Aptos ecosystem
"""

import asyncio
import json
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
import logging
import time
import requests
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account
from aptos_sdk.transactions import EntryFunction, TransactionPayload

@dataclass
class AptosTransaction:
    """Data class for Aptos transactions"""
    function: str
    type_arguments: List[str]
    arguments: List[Any]
    max_gas_amount: int = 10000
    gas_unit_price: int = 100

class AptosConnector:
    """
    Aptos network connector for real interactions
    """
    
    def __init__(self, config):
        self.config = config
        self.network = config.get("aptos", {}).get("network", "mainnet")
        self.logger = logging.getLogger(__name__)
        
        # Real Aptos endpoints
        if self.network == "mainnet":
            self.rpc_url = "https://fullnode.mainnet.aptoslabs.com/v1"
            self.faucet_url = None  # No faucet on mainnet
        elif self.network == "testnet":
            self.rpc_url = "https://fullnode.testnet.aptoslabs.com/v1"
            self.faucet_url = "https://faucet.testnet.aptoslabs.com"
        else:  # devnet
            self.rpc_url = "https://fullnode.devnet.aptoslabs.com/v1"
            self.faucet_url = "https://faucet.devnet.aptoslabs.com"
        
        # Initialize Aptos client
        try:
            self.client = RestClient(self.rpc_url)
            self.connected = True
            self.logger.info(f"Aptos connection established: {self.network}")
        except Exception as e:
            self.connected = False
            self.logger.error(f"Failed to connect to Aptos: {e}")
        
        # Real contract addresses - these would be actual deployed contracts
        self.trading_contract = config.get("trading_contract", "0x1")
        self.vault_contract = config.get("vault_contract", "0x1")
        
        # Account will be set when user authenticates
        self.account = None
        
        # Alternative RPC endpoints for failover
        self.backup_rpcs = [
            "https://aptos-mainnet.pontem.network",
            "https://rpc.ankr.com/http/aptos/v1",
            "https://aptos.rpcpool.com/v1"
        ]
        self.current_rpc_index = 0
    
    async def initialize_account(self, private_key: str = None) -> Dict:
        """Initialize account from private key or create new one"""
        try:
            if private_key:
                # Load existing account
                self.account = Account.load_key(private_key)
                self.logger.info(f"Account loaded: {self.account.address()}")
            else:
                # Create new account
                self.account = Account.generate()
                self.logger.info(f"New account created: {self.account.address()}")
                
                # Fund account on testnet/devnet
                if self.network != "mainnet" and self.faucet_url:
                    await self._fund_account()
            
            # Get account info
            account_info = await self.get_account_info()
            
            return {
                "status": "success",
                "address": str(self.account.address()),
                "private_key": self.account.private_key.hex() if not private_key else "***",
                "balance": account_info.get("balance", 0),
                "sequence_number": account_info.get("sequence_number", 0)
            }
            
        except Exception as e:
            self.logger.error(f"Account initialization error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            if not self.account:
                return {"error": "No account initialized"}
            
            # Get account resources
            resources = await self.client.account_resources(self.account.address())
            
            # Extract APT balance
            apt_balance = 0
            for resource in resources:
                if resource["type"] == "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>":
                    apt_balance = int(resource["data"]["coin"]["value"]) / 100000000  # Convert from octas
                    break
            
            # Get account data
            account_data = await self.client.account(self.account.address())
            
            return {
                "address": str(self.account.address()),
                "balance": apt_balance,
                "sequence_number": int(account_data.get("sequence_number", 0)),
                "authentication_key": account_data.get("authentication_key", ""),
                "resources_count": len(resources)
            }
            
        except Exception as e:
            self.logger.error(f"Get account info error: {e}")
            return {"error": str(e)}
    
    async def transfer_apt(self, to_address: str, amount: float) -> Dict:
        """Transfer APT tokens"""
        try:
            if not self.account:
                return {"status": "error", "message": "No account initialized"}
            
            # Convert APT to octas (1 APT = 100,000,000 octas)
            amount_octas = int(amount * 100000000)
            
            # Create transfer transaction
            payload = EntryFunction.natural(
                "0x1::coin",
                "transfer",
                ["0x1::aptos_coin::AptosCoin"],
                [to_address, amount_octas]
            )
            
            # Submit transaction
            txn_request = await self.client.create_bcs_transaction(self.account, payload)
            signed_txn = self.account.sign(txn_request)
            tx_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for transaction confirmation
            await self.client.wait_for_transaction(tx_hash)
            
            return {
                "status": "success",
                "tx_hash": tx_hash,
                "amount": amount,
                "to_address": to_address,
                "gas_used": "estimated"
            }
            
        except Exception as e:
            self.logger.error(f"Transfer error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_trading_transaction(self, transaction: AptosTransaction) -> Dict:
        """Execute a trading-related transaction"""
        try:
            if not self.account:
                return {"status": "error", "message": "No account initialized"}
            
            # Create entry function payload
            payload = EntryFunction.natural(
                transaction.function,
                transaction.function.split("::")[-1],  # Extract function name
                transaction.type_arguments,
                transaction.arguments
            )
            
            # Create and submit transaction
            txn_request = await self.client.create_bcs_transaction(
                self.account, 
                payload,
                max_gas_amount=transaction.max_gas_amount,
                gas_unit_price=transaction.gas_unit_price
            )
            
            signed_txn = self.account.sign(txn_request)
            tx_hash = await self.client.submit_bcs_transaction(signed_txn)
            
            # Wait for confirmation
            await self.client.wait_for_transaction(tx_hash)
            
            # Get transaction details
            tx_details = await self.client.transaction_by_hash(tx_hash)
            
            return {
                "status": "success",
                "tx_hash": tx_hash,
                "gas_used": tx_details.get("gas_used", "unknown"),
                "success": tx_details.get("success", True),
                "vm_status": tx_details.get("vm_status", "executed")
            }
            
        except Exception as e:
            self.logger.error(f"Trading transaction error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_token_balance(self, token_address: str) -> Dict:
        """Get balance of a specific token"""
        try:
            if not self.account:
                return {"error": "No account initialized"}
            
            # Get account resources
            resources = await self.client.account_resources(self.account.address())
            
            # Look for the specific token
            coin_store_type = f"0x1::coin::CoinStore<{token_address}>"
            
            for resource in resources:
                if resource["type"] == coin_store_type:
                    balance = int(resource["data"]["coin"]["value"])
                    return {
                        "token_address": token_address,
                        "balance": balance,
                        "balance_formatted": balance / 100000000  # Assuming 8 decimals
                    }
            
            return {
                "token_address": token_address,
                "balance": 0,
                "balance_formatted": 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Token balance error: {e}")
            return {"error": str(e)}
    
    async def get_transaction_history(self, limit: int = 25) -> Dict:
        """Get transaction history for the account"""
        try:
            if not self.account:
                return {"error": "No account initialized"}
            
            # Get account transactions
            transactions = await self.client.account_transactions(
                self.account.address(), 
                limit=limit
            )
            
            formatted_txs = []
            for tx in transactions:
                formatted_txs.append({
                    "hash": tx.get("hash", ""),
                    "type": tx.get("type", ""),
                    "success": tx.get("success", False),
                    "gas_used": tx.get("gas_used", 0),
                    "gas_unit_price": tx.get("gas_unit_price", 0),
                    "timestamp": tx.get("timestamp", ""),
                    "version": tx.get("version", 0)
                })
            
            return {
                "status": "success",
                "transaction_count": len(formatted_txs),
                "transactions": formatted_txs
            }
            
        except Exception as e:
            self.logger.error(f"Transaction history error: {e}")
            return {"error": str(e)}
    
    async def get_network_info(self) -> Dict:
        """Get current network information"""
        try:
            # Get ledger info
            ledger_info = await self.client.ledger_info()
            
            # Get node info
            node_info = await self.client.info()
            
            return {
                "network": self.network,
                "chain_id": ledger_info.get("chain_id", 0),
                "ledger_version": ledger_info.get("ledger_version", 0),
                "ledger_timestamp": ledger_info.get("ledger_timestamp", ""),
                "node_role": node_info.get("role_type", "unknown"),
                "api_version": node_info.get("api_version", "unknown")
            }
            
        except Exception as e:
            self.logger.error(f"Network info error: {e}")
            return {"error": str(e)}
    
    async def estimate_gas(self, transaction: AptosTransaction) -> Dict:
        """Estimate gas for a transaction"""
        try:
            if not self.account:
                return {"error": "No account initialized"}
            
            # Create payload for estimation
            payload = EntryFunction.natural(
                transaction.function,
                transaction.function.split("::")[-1],
                transaction.type_arguments,
                transaction.arguments
            )
            
            # Simulate transaction to get gas estimate
            txn_request = await self.client.create_bcs_transaction(
                self.account, 
                payload,
                max_gas_amount=transaction.max_gas_amount,
                gas_unit_price=transaction.gas_unit_price
            )
            
            # Simulate the transaction
            simulation = await self.client.simulate_transaction(self.account, txn_request)
            
            if simulation and len(simulation) > 0:
                sim_result = simulation[0]
                return {
                    "estimated_gas": sim_result.get("gas_used", transaction.max_gas_amount),
                    "gas_unit_price": transaction.gas_unit_price,
                    "estimated_cost": int(sim_result.get("gas_used", transaction.max_gas_amount)) * transaction.gas_unit_price,
                    "success": sim_result.get("success", False)
                }
            
            return {
                "estimated_gas": transaction.max_gas_amount,
                "gas_unit_price": transaction.gas_unit_price,
                "estimated_cost": transaction.max_gas_amount * transaction.gas_unit_price,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Gas estimation error: {e}")
            return {"error": str(e)}
    
    async def get_market_data(self) -> Dict:
        """Get current market data for APT"""
        try:
            # Get real market data from CoinGecko API
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # Get price and basic data
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=aptos&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true") as response:
                    if response.status == 200:
                        price_data = await response.json()
                        aptos_data = price_data.get("aptos", {})
                        
                        # Get additional coin data
                        async with session.get("https://api.coingecko.com/api/v3/coins/aptos") as coin_response:
                            if coin_response.status == 200:
                                coin_data = await coin_response.json()
                                market_data = coin_data.get("market_data", {})
                                
                                return {
                                    "apt_price_usd": aptos_data.get("usd", 0),
                                    "24h_change": aptos_data.get("usd_24h_change", 0),
                                    "24h_volume": aptos_data.get("usd_24h_vol", 0),
                                    "market_cap": aptos_data.get("usd_market_cap", 0),
                                    "circulating_supply": market_data.get("circulating_supply", 0),
                                    "total_supply": market_data.get("total_supply", 0),
                                    "max_supply": market_data.get("max_supply", 0),
                                    "ath": market_data.get("ath", {}).get("usd", 0),
                                    "atl": market_data.get("atl", {}).get("usd", 0)
                                }
            
            # Fallback if API fails
            return {
                "apt_price_usd": 12.50,
                "24h_change": 0,
                "24h_volume": 0,
                "market_cap": 0,
                "circulating_supply": 0,
                "total_supply": 0,
                "error": "API unavailable"
            }
            
        except Exception as e:
            self.logger.error(f"Market data error: {e}")
            return {"error": str(e)}
    
    async def _fund_account(self) -> bool:
        """Fund account using faucet (testnet/devnet only)"""
        try:
            if not self.faucet_url or not self.account:
                return False
            
            faucet_request = {
                "address": str(self.account.address()),
                "amount": 100000000  # 1 APT in octas
            }
            
            response = requests.post(
                f"{self.faucet_url}/mint",
                json=faucet_request,
                timeout=30
            )
            
            if response.status_code == 200:
                self.logger.info("Account funded successfully")
                return True
            else:
                self.logger.error(f"Faucet request failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Faucet error: {e}")
            return False
    
    async def switch_rpc(self) -> bool:
        """Switch to backup RPC endpoint"""
        try:
            if self.current_rpc_index < len(self.backup_rpcs) - 1:
                self.current_rpc_index += 1
                new_rpc = self.backup_rpcs[self.current_rpc_index]
                
                # Create new client with backup RPC
                self.client = RestClient(new_rpc)
                self.rpc_url = new_rpc
                
                self.logger.info(f"Switched to backup RPC: {new_rpc}")
                return True
            else:
                self.logger.error("No more backup RPCs available")
                return False
                
        except Exception as e:
            self.logger.error(f"RPC switch error: {e}")
            return False
    
    async def health_check(self) -> Dict:
        """Check the health of the connection"""
        try:
            # Try to get ledger info
            ledger_info = await self.client.ledger_info()
            
            if ledger_info:
                return {
                    "status": "healthy",
                    "rpc_url": self.rpc_url,
                    "network": self.network,
                    "latest_version": ledger_info.get("ledger_version", 0),
                    "response_time": "fast"
                }
            else:
                return {
                    "status": "unhealthy",
                    "rpc_url": self.rpc_url,
                    "error": "No response from RPC"
                }
                
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            return {
                "status": "unhealthy",
                "rpc_url": self.rpc_url,
                "error": str(e)
            }

# Utility functions for common operations
async def create_aptos_connector(config: Dict) -> AptosConnector:
    """Create and initialize Aptos connector"""
    connector = AptosConnector(config)
    
    # Initialize with existing private key if provided
    private_key = config.get("private_key")
    if private_key:
        await connector.initialize_account(private_key)
    
    return connector

async def execute_batch_transactions(connector: AptosConnector, transactions: List[AptosTransaction]) -> List[Dict]:
    """Execute multiple transactions in sequence"""
    results = []
    
    for tx in transactions:
        result = await connector.execute_trading_transaction(tx)
        results.append(result)
        
        # Small delay between transactions
        await asyncio.sleep(1)
    
    return results

# Integration with main trading bot
class AptosNetworkManager:
    """Manager for Aptos network operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.connector = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> Dict:
        """Initialize the network manager"""
        try:
            self.connector = await create_aptos_connector(self.config)
            
            if self.connector.connected:
                return {
                    "status": "success",
                    "network": self.connector.network,
                    "rpc_url": self.connector.rpc_url
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to connect to Aptos network"
                }
                
        except Exception as e:
            self.logger.error(f"Network manager initialization error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_connector(self) -> Optional[AptosConnector]:
        """Get the network connector"""
        return self.connector
    
    async def execute_strategy_transaction(self, strategy_name: str, params: Dict) -> Dict:
        """Execute a strategy-specific transaction"""
        try:
            if not self.connector:
                return {"status": "error", "message": "Network not initialized"}
            
            # Map strategy to contract function
            strategy_functions = {
                "stake": f"{self.connector.trading_contract}::staking::stake",
                "unstake": f"{self.connector.trading_contract}::staking::unstake",
                "provide_liquidity": f"{self.connector.trading_contract}::dex::add_liquidity",
                "remove_liquidity": f"{self.connector.trading_contract}::dex::remove_liquidity",
                "swap": f"{self.connector.trading_contract}::dex::swap",
                "deposit_vault": f"{self.connector.vault_contract}::vault::deposit",
                "withdraw_vault": f"{self.connector.vault_contract}::vault::withdraw"
            }
            
            function = strategy_functions.get(strategy_name)
            if not function:
                return {"status": "error", "message": f"Unknown strategy: {strategy_name}"}
            
            # Create transaction
            transaction = AptosTransaction(
                function=function,
                type_arguments=params.get("type_arguments", []),
                arguments=params.get("arguments", []),
                max_gas_amount=params.get("max_gas", 10000),
                gas_unit_price=params.get("gas_price", 100)
            )
            
            # Execute transaction
            result = await self.connector.execute_trading_transaction(transaction)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Strategy transaction error: {e}")
            return {"status": "error", "message": str(e)}

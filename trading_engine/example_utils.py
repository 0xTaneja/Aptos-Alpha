"""
Aptos Example Utilities
Provides setup functions for Aptos SDK integration and account management
"""

import json
import os
import logging
from typing import Dict, List, Optional, Tuple
from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account import Account as AptosAccount
from aptos_sdk.ed25519 import PrivateKey

logger = logging.getLogger(__name__)

async def setup_aptos(node_url: str = None, faucet_url: str = None, config_path: str = None) -> Tuple[str, RestClient, AptosAccount]:
    """
    Setup Aptos client and account for trading operations
    
    Args:
        node_url: Aptos node URL (defaults to testnet)
        faucet_url: Faucet URL for testnet funding
        config_path: Path to configuration file
        
    Returns:
        Tuple of (address, client, account)
    """
    try:
        # Set default URLs
        if not node_url:
            node_url = "https://fullnode.testnet.aptoslabs.com/v1"
        if not faucet_url:
            faucet_url = "https://faucet.testnet.aptoslabs.com"
        
        # Initialize Aptos client
        client = RestClient(node_url)
        
        # Load or create account
        if config_path and os.path.exists(config_path):
            # Load from config file
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            private_key_hex = config.get("private_key")
            if private_key_hex:
                # Load existing account
                private_key = PrivateKey.from_hex(private_key_hex)
                account = AptosAccount(private_key)
            else:
                # Generate new account
                account = AptosAccount.generate()
                # Save to config
                config["private_key"] = account.private_key.hex()
                config["address"] = str(account.address())
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
        else:
            # Generate new account
            account = AptosAccount.generate()
            
            # Create config file if path provided
            if config_path:
                config = {
                    "private_key": account.private_key.hex(),
                    "address": str(account.address()),
                    "node_url": node_url,
                    "faucet_url": faucet_url
                }
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
        
        address = str(account.address())
        logger.info(f"Aptos account setup: {address}")
        
        # Check account balance
        try:
            balance = client.account_balance(address)
            balance_apt = balance / 100_000_000  # Convert from octas to APT
            logger.info(f"Account balance: {balance_apt:.8f} APT")
            
            # Fund account if balance is too low and on testnet
            if balance_apt < 1.0 and "testnet" in node_url:
                logger.info("Low balance detected, attempting to fund from faucet...")
                await fund_account_testnet(client, account, faucet_url)
                
        except ApiError as e:
            logger.warning(f"Could not check account balance: {e}")
            # Account might not exist yet, try to fund it
            if "testnet" in node_url:
                logger.info("Account not found, attempting to fund from faucet...")
                await fund_account_testnet(client, account, faucet_url)
        
        return address, client, account
        
    except Exception as e:
        logger.error(f"Error setting up Aptos: {e}")
        raise

async def fund_account_testnet(client: RestClient, account: AptosAccount, faucet_url: str, amount: int = 100_000_000):
    """
    Fund account from testnet faucet
    
    Args:
        client: Aptos REST client
        account: Account to fund
        faucet_url: Faucet URL
        amount: Amount in octas (default 1 APT)
    """
    try:
        import requests
        
        address = str(account.address())
        
        # Request funding from faucet
        response = requests.post(
            f"{faucet_url}/mint",
            params={
                "address": address,
                "amount": amount
            },
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully funded account {address} with {amount / 100_000_000} APT")
            
            # Wait for transaction to be processed
            import asyncio
            await asyncio.sleep(2)
            
            # Verify funding
            balance = client.account_balance(address)
            logger.info(f"New balance: {balance / 100_000_000:.8f} APT")
        else:
            logger.warning(f"Faucet funding failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error funding account: {e}")

def setup_multi_account_wallets(config_path: str) -> List[AptosAccount]:
    """
    Setup multiple Aptos accounts for multi-signature operations
    
    Args:
        config_path: Path to configuration file containing multiple accounts
        
    Returns:
        List of AptosAccount objects
    """
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)

        accounts = []
        multi_sig_config = config.get("multi_sig", {})
        authorized_users = multi_sig_config.get("authorized_users", [])
        
        for i, user_config in enumerate(authorized_users):
            private_key_hex = user_config.get("private_key")
            expected_address = user_config.get("address")
            
            if not private_key_hex:
                raise ValueError(f"Missing private_key for user {i}")
            
            # Create account from private key
            private_key = PrivateKey.from_hex(private_key_hex)
            account = AptosAccount(private_key)
            actual_address = str(account.address())
            
            # Verify address matches if provided
            if expected_address and actual_address != expected_address:
                raise ValueError(f"Address mismatch for user {i}: expected {expected_address}, got {actual_address}")
            
            accounts.append(account)
            logger.info(f"Loaded authorized user for multi-sig: {actual_address}")
        
        return accounts
        
    except Exception as e:
        logger.error(f"Error setting up multi-account wallets: {e}")
        raise

def create_example_config(config_path: str, node_url: str = None, faucet_url: str = None) -> Dict:
    """
    Create example configuration file for Aptos trading bot
    
    Args:
        config_path: Path where to create the config file
        node_url: Aptos node URL
        faucet_url: Faucet URL for testnet
        
    Returns:
        Configuration dictionary
    """
    try:
        # Generate new account for the config
        account = AptosAccount.generate()
        
        # Set default URLs
        if not node_url:
            node_url = "https://fullnode.testnet.aptoslabs.com/v1"
        if not faucet_url:
            faucet_url = "https://faucet.testnet.aptoslabs.com"
        
        config = {
            "private_key": account.private_key.hex(),
            "address": str(account.address()),
            "node_url": node_url,
            "faucet_url": faucet_url,
            "trading": {
                "max_position_size": 1000,  # APT
                "default_slippage": 0.005,  # 0.5%
                "gas_unit_price": 100,      # octas per gas unit
                "max_gas_amount": 10000     # maximum gas per transaction
            },
            "dex_contracts": {
                "pancakeswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",
                "thala": "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af",
                "liquidswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12"
            },
            "multi_sig": {
                "enabled": False,
                "threshold": 2,
                "authorized_users": [
                    {
                        "private_key": AptosAccount.generate().private_key.hex(),
                        "address": str(AptosAccount.generate().address()),
                        "role": "trader"
                    },
                    {
                        "private_key": AptosAccount.generate().private_key.hex(),
                        "address": str(AptosAccount.generate().address()),
                        "role": "admin"
                    }
                ]
            }
        }
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Write config file
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Created example config at: {config_path}")
        return config
        
    except Exception as e:
        logger.error(f"Error creating example config: {e}")
        raise

async def get_account_info(client: RestClient, address: str) -> Dict:
    """
    Get comprehensive account information
    
    Args:
        client: Aptos REST client
        address: Account address
        
    Returns:
        Dictionary with account information
    """
    try:
        # Get basic account info
        account_data = client.account(address)
        
        # Get balance
        balance = client.account_balance(address)
        
        # Get resources
        resources = client.account_resources(address)
        
        # Parse token balances
        token_balances = {}
        for resource in resources:
            if "CoinStore" in resource["type"]:
                type_parts = resource["type"].split("<")
                if len(type_parts) > 1:
                    token_type = type_parts[1].split(">")[0]
                    coin_data = resource["data"]["coin"]
                    balance_raw = int(coin_data["value"])
                    
                    if balance_raw > 0:
                        token_symbol = token_type.split("::")[-1]
                        token_balances[token_symbol] = {
                            "balance": balance_raw,
                            "balance_formatted": balance_raw / 100_000_000,
                            "token_type": token_type
                        }
        
        return {
            "address": address,
            "sequence_number": account_data.get("sequence_number"),
            "authentication_key": account_data.get("authentication_key"),
            "apt_balance": balance,
            "apt_balance_formatted": balance / 100_000_000,
            "token_balances": token_balances,
            "resource_count": len(resources)
        }
        
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        return {"error": str(e)}

async def transfer_apt(client: RestClient, sender: AptosAccount, recipient_address: str, amount: int) -> Dict:
    """
    Transfer APT between accounts
    
    Args:
        client: Aptos REST client
        sender: Sender account
        recipient_address: Recipient address
        amount: Amount in octas
        
    Returns:
        Transaction result
    """
    try:
        from aptos_sdk.transactions import EntryFunction, TransactionArgument, TransactionPayload, Serializer
        
        # Create transfer transaction
        payload = EntryFunction.natural(
            "0x1::aptos_account",
            "transfer",
            [],
            [
                TransactionArgument(recipient_address, Serializer.str),
                TransactionArgument(amount, Serializer.u64),
            ]
        )
        
        # Submit transaction
        txn = client.create_bcs_transaction(sender, TransactionPayload(payload))
        signed_txn = sender.sign(txn)
        txn_hash = client.submit_bcs_transaction(signed_txn)
        
        # Wait for confirmation
        client.wait_for_transaction(txn_hash)
        
        logger.info(f"Successfully transferred {amount / 100_000_000} APT to {recipient_address}")
        
        return {
            "status": "success",
            "txn_hash": txn_hash,
            "amount": amount,
            "amount_apt": amount / 100_000_000,
            "recipient": recipient_address
        }
        
    except Exception as e:
        logger.error(f"Error transferring APT: {e}")
        return {"status": "error", "message": str(e)}

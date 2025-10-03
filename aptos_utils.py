"""
Aptos utilities for setup and configuration
Equivalent to Hyperliquid's example_utils.py but for Aptos
"""

import json
import os
import logging
from typing import Tuple, List, Optional

from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient

from aptos.exchange import AptosExchange
from aptos.info import AptosInfo

logger = logging.getLogger(__name__)

async def setup(
    node_url: Optional[str] = None,
    config_path: Optional[str] = None,
    network: str = "testnet"
) -> Tuple[str, AptosInfo, AptosExchange]:
    """
    Setup Aptos connection with account from config
    
    Args:
        node_url: Aptos node URL (optional)
        config_path: Path to config file (optional)
        network: Network to connect to (testnet/mainnet)
    
    Returns:
        Tuple of (address, info, exchange)
    """
    # Default paths and URLs
    if not config_path:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    if not node_url:
        if network == "mainnet":
            node_url = "https://fullnode.mainnet.aptoslabs.com/v1"
        else:
            node_url = "https://fullnode.testnet.aptoslabs.com/v1"
    
    # Load configuration
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise Exception(f"Config file not found: {config_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise Exception(f"Invalid JSON in config file: {e}")
    
    # Get Aptos configuration
    aptos_config = config.get("aptos", {})
    if not aptos_config:
        # Try general config
        general_config = config.get("general", {})
        private_key = general_config.get("admin_private_key") or config.get("private_key")
        account_address = general_config.get("account_address") or config.get("account_address")
    else:
        private_key = aptos_config.get("admin_private_key") or aptos_config.get("private_key")
        account_address = aptos_config.get("account_address")
    
    if not private_key:
        logger.error("No private key found in config")
        raise Exception("No private key found in config. Please add 'private_key' or 'admin_private_key' to your config.")
    
    # Create account from private key
    try:
        if private_key.startswith('0x'):
            private_key = private_key[2:]  # Remove 0x prefix if present
        account = Account.load_key(private_key)
    except Exception as e:
        logger.error(f"Invalid private key: {e}")
        raise Exception(f"Invalid private key format: {e}")
    
    # Determine address
    derived_address = str(account.address())
    if account_address and account_address != "":
        if account_address != derived_address:
            logger.warning(f"Config address {account_address} differs from derived address {derived_address}")
            logger.warning("Using derived address from private key")
        address = derived_address
    else:
        address = derived_address
    
    print(f"Running with Aptos account address: {address}")
    print(f"Network: {network}")
    print(f"Node URL: {node_url}")
    
    # Initialize info and exchange
    info = AptosInfo(node_url)
    exchange = AptosExchange(account, node_url)
    
    # Check account has balance
    try:
        balance = await info.get_account_balance(address)
        portfolio = await info.get_account_portfolio(address)
        
        if balance == 0 and portfolio.get("total_value_usd", 0) == 0:
            logger.warning("Account has no APT balance")
            
            # For testnet, try to fund from faucet
            if network == "testnet":
                print("Attempting to fund account from testnet faucet...")
                try:
                    await fund_from_faucet(address)
                    # Wait a bit and check again
                    import asyncio
                    await asyncio.sleep(5)
                    balance = await info.get_account_balance(address)
                    if balance > 0:
                        print(f"Successfully funded account with {balance / 100000000:.8f} APT")
                    else:
                        print("Faucet funding may have failed or is still processing")
                except Exception as e:
                    logger.warning(f"Faucet funding failed: {e}")
            
            if balance == 0:
                error_string = f"""
No APT balance found for account {address}

If you think this is a mistake, make sure that {address} has APT balance on {network}.

For testnet: Visit https://faucet.testnet.aptoslabs.com to fund your account
For mainnet: Transfer APT to your account address

Current balance: {balance / 100000000:.8f} APT
"""
                print(error_string)
                # Don't raise exception, just warn - account might still be usable
                logger.warning("Account has no balance but continuing anyway")
        else:
            print(f"Account balance: {balance / 100000000:.8f} APT")
            if portfolio.get("total_value_usd"):
                print(f"Portfolio value: ${portfolio['total_value_usd']:.2f}")
    
    except Exception as e:
        logger.warning(f"Could not check account balance: {e}")
        print("Continuing without balance check...")
    
    return address, info, exchange

async def fund_from_faucet(address: str, amount: int = 100000000) -> bool:
    """
    Fund account from Aptos testnet faucet
    
    Args:
        address: Account address to fund
        amount: Amount in octas (default 1 APT)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import aiohttp
        
        faucet_url = "https://faucet.testnet.aptoslabs.com"
        
        async with aiohttp.ClientSession() as session:
            faucet_request = {
                "address": address,
                "amount": amount
            }
            
            async with session.post(faucet_url, json=faucet_request) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Faucet funding successful: {result}")
                    return True
                else:
                    logger.error(f"Faucet funding failed: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"Faucet funding error: {e}")
        return False

def generate_new_account() -> Tuple[Account, str]:
    """
    Generate a new Aptos account
    
    Returns:
        Tuple of (account, address)
    """
    account = Account.generate()
    address = str(account.address())
    
    print(f"Generated new Aptos account:")
    print(f"Address: {address}")
    print(f"Private Key: 0x{account.private_key.hex()}")
    print(f"Public Key: 0x{account.public_key.hex()}")
    print("\n⚠️  IMPORTANT: Save your private key securely!")
    print("⚠️  Never share your private key with anyone!")
    
    return account, address

def save_account_config(
    account: Account,
    config_path: str = "wallet_config.json",
    network: str = "testnet"
) -> str:
    """
    Save account configuration to file
    
    Args:
        account: Aptos account to save
        config_path: Path to save config file
        network: Network name
    
    Returns:
        Path to saved config file
    """
    config = {
        "address": str(account.address()),
        "private_key": f"0x{account.private_key.hex()}",
        "public_key": f"0x{account.public_key.hex()}",
        "network": network,
        "created_at": int(time.time())
    }
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Account configuration saved to: {config_path}")
    return config_path

def load_account_from_config(config_path: str) -> Tuple[Account, str]:
    """
    Load account from configuration file
    
    Args:
        config_path: Path to config file
    
    Returns:
        Tuple of (account, address)
    """
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        private_key = config.get("private_key", "")
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        
        account = Account.load_key(private_key)
        address = str(account.address())
        
        # Verify address matches config
        config_address = config.get("address", "")
        if config_address and config_address != address:
            logger.warning(f"Config address {config_address} differs from derived {address}")
        
        return account, address
        
    except Exception as e:
        logger.error(f"Failed to load account from config: {e}")
        raise

async def setup_multi_accounts(config_path: str) -> List[Tuple[Account, str]]:
    """
    Setup multiple accounts from configuration
    
    Args:
        config_path: Path to config file with multiple accounts
    
    Returns:
        List of (account, address) tuples
    """
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        accounts = []
        multi_account_config = config.get("multi_accounts", [])
        
        for i, account_config in enumerate(multi_account_config):
            private_key = account_config.get("private_key", "")
            if private_key.startswith('0x'):
                private_key = private_key[2:]
            
            account = Account.load_key(private_key)
            address = str(account.address())
            
            # Verify address if provided
            config_address = account_config.get("address", "")
            if config_address and config_address != address:
                raise Exception(f"Account {i}: provided address {config_address} does not match private key")
            
            accounts.append((account, address))
            print(f"Loaded account {i}: {address}")
        
        return accounts
        
    except Exception as e:
        logger.error(f"Failed to setup multi-accounts: {e}")
        raise

def create_default_config(
    private_key: str = None,
    network: str = "testnet",
    config_path: str = "config.json"
) -> str:
    """
    Create default configuration file
    
    Args:
        private_key: Private key to use (generates new if None)
        network: Network to configure for
        config_path: Path to save config
    
    Returns:
        Path to created config file
    """
    import time
    
    # Generate account if no private key provided
    if not private_key:
        account = Account.generate()
        private_key = f"0x{account.private_key.hex()}"
        address = str(account.address())
        print(f"Generated new account: {address}")
    else:
        if private_key.startswith('0x'):
            pk = private_key[2:]
        else:
            pk = private_key
        account = Account.load_key(pk)
        address = str(account.address())
    
    # Create configuration
    config = {
        "general": {
            "environment": network,
            "node_url": "https://fullnode.testnet.aptoslabs.com/v1" if network == "testnet" else "https://fullnode.mainnet.aptoslabs.com/v1",
            "faucet_url": "https://faucet.testnet.aptoslabs.com" if network == "testnet" else None
        },
        "aptos": {
            "admin_private_key": private_key,
            "account_address": address,
            "network": network
        },
        "telegram_bot": {
            "bot_token": "YOUR_BOT_TOKEN_HERE",
            "allowed_users": [],
            "admin_users": []
        },
        "trading": {
            "default_slippage": 0.05,
            "max_gas_amount": 10000,
            "gas_unit_price": 100
        },
        "created_at": int(time.time())
    }
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Default configuration created: {config_path}")
    print(f"Account address: {address}")
    print(f"Network: {network}")
    
    if network == "testnet":
        print(f"\n💡 To fund your testnet account, visit:")
        print(f"   https://faucet.testnet.aptoslabs.com")
        print(f"   Address: {address}")
    
    return config_path

# Convenience function for quick testing
async def quick_setup(network: str = "testnet") -> Tuple[str, AptosInfo, AptosExchange]:
    """
    Quick setup for testing - creates config if needed
    
    Args:
        network: Network to use (testnet/mainnet)
    
    Returns:
        Tuple of (address, info, exchange)
    """
    config_path = "config.json"
    
    # Create default config if it doesn't exist
    if not os.path.exists(config_path):
        print("No config found, creating default configuration...")
        create_default_config(network=network, config_path=config_path)
    
    return await setup(network=network, config_path=config_path)

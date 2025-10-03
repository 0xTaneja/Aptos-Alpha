import json
import os
import sys

from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient

# Re-export everything for backward compatibility
__all__ = ['setup', 'setup_multi_account_wallets']


def setup(base_url=None, network="mainnet"):
    """
    Setup Aptos client and account for examples
    
    Args:
        base_url: Aptos RPC URL (optional)
        network: Network to connect to (mainnet, testnet, devnet)
    """
    config_path = os.path.join(os.path.dirname(__file__), "..", "bot_config.json")
    
    # Try to load config, create default if not exists
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        # Create default config
        config = {
            "aptos": {
                "network": network,
                "private_key": None,
                "account_address": ""
            }
        }
        print("Config file not found, using defaults")
    
    # Determine RPC URL
    if base_url:
        rpc_url = base_url
    else:
        if network == "mainnet":
            rpc_url = "https://fullnode.mainnet.aptoslabs.com/v1"
        elif network == "testnet":
            rpc_url = "https://fullnode.testnet.aptoslabs.com/v1"
        else:  # devnet
            rpc_url = "https://fullnode.devnet.aptoslabs.com/v1"
    
    # Initialize client
    client = RestClient(rpc_url)
    
    # Initialize account
    private_key = config.get("aptos", {}).get("private_key")
    if private_key:
        account = Account.load_key(private_key)
    else:
        # Generate new account for examples
        account = Account.generate()
        print(f"Generated new account: {account.address()}")
        print(f"Private key: {account.private_key.hex()}")
        print("⚠️  Save this private key securely!")
    
    address = str(account.address())
    print("Running with account address:", address)
    
    # Check account balance
    try:
        resources = client.account_resources(account.address())
        apt_balance = 0
        
        for resource in resources:
            if resource["type"] == "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>":
                apt_balance = int(resource["data"]["coin"]["value"]) / 100000000
                break
        
        if apt_balance == 0:
            if network != "mainnet":
                print("Account has no APT balance. Consider using the faucet:")
                print(f"https://faucet.{network}.aptoslabs.com")
            else:
                print("Account has no APT balance. Please fund the account to run examples.")
            
            error_string = f"No APT balance:\nAccount {address} has no APT balance on {network}.\nPlease fund the account or use testnet/devnet with faucet."
            raise Exception(error_string)
        
        print(f"Account balance: {apt_balance} APT")
        
    except Exception as e:
        print(f"Could not check account balance: {e}")
        if network == "mainnet":
            raise Exception("Cannot verify account balance on mainnet")
    
    return address, client, account


def setup_multi_account_wallets():
    """
    Setup multiple Aptos accounts for multi-signature examples
    """
    config_path = os.path.join(os.path.dirname(__file__), "..", "bot_config.json")
    
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        raise Exception("Config file not found. Please create bot_config.json with multi_account configuration.")
    
    if "multi_account" not in config:
        raise Exception("multi_account configuration not found in config file")
    
    authorized_accounts = []
    for account_config in config["multi_account"]["authorized_accounts"]:
        private_key = account_config["private_key"]
        expected_address = account_config.get("account_address", "")
        
        account = Account.load_key(private_key)
        actual_address = str(account.address())
        
        if expected_address and expected_address != actual_address:
            raise Exception(f"Provided address {expected_address} does not match private key")
        
        print("Loaded authorized account for multi-sig:", actual_address)
        authorized_accounts.append(account)
    
    return authorized_accounts


def create_example_config():
    """Create an example configuration file"""
    config = {
        "aptos": {
            "network": "testnet",
            "private_key": None,
            "account_address": ""
        },
        "multi_account": {
            "authorized_accounts": [
                {
                    "private_key": "0x...",
                    "account_address": "0x..."
                }
            ]
        },
        "trading": {
            "contract_address": "0x1",
            "vault_address": "0x1",
            "max_gas_amount": 10000,
            "gas_unit_price": 100
        }
    }
    
    config_path = os.path.join(os.path.dirname(__file__), "..", "bot_config.json")
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Example config created at: {config_path}")
    print("Please update the configuration with your actual values.")


def fund_account_testnet(account: Account):
    """
    Fund account using testnet faucet
    """
    import requests
    
    try:
        faucet_url = "https://faucet.testnet.aptoslabs.com"
        response = requests.post(
            f"{faucet_url}/mint",
            json={
                "address": str(account.address()),
                "amount": 100000000  # 1 APT
            },
            timeout=30
        )
        
        if response.status_code == 200:
            print("Account funded successfully with 1 APT")
            return True
        else:
            print(f"Faucet request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error funding account: {e}")
        return False


def get_account_info(client: RestClient, account: Account):
    """
    Get detailed account information
    """
    try:
        address = account.address()
        
        # Get account data
        account_data = client.account(address)
        
        # Get resources
        resources = client.account_resources(address)
        
        # Extract APT balance
        apt_balance = 0
        for resource in resources:
            if resource["type"] == "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>":
                apt_balance = int(resource["data"]["coin"]["value"]) / 100000000
                break
        
        return {
            "address": str(address),
            "sequence_number": account_data.get("sequence_number", 0),
            "authentication_key": account_data.get("authentication_key", ""),
            "apt_balance": apt_balance,
            "resources_count": len(resources)
        }
        
    except Exception as e:
        print(f"Error getting account info: {e}")
        return None


# Utility functions for common operations
def transfer_apt(client: RestClient, sender: Account, recipient_address: str, amount: float):
    """
    Transfer APT tokens between accounts
    """
    from aptos_sdk.transactions import EntryFunction
    
    try:
        # Convert APT to octas
        amount_octas = int(amount * 100000000)
        
        # Create transfer payload
        payload = EntryFunction.natural(
            "0x1::coin",
            "transfer",
            ["0x1::aptos_coin::AptosCoin"],
            [recipient_address, amount_octas]
        )
        
        # Submit transaction
        txn_request = client.create_bcs_transaction(sender, payload)
        signed_txn = sender.sign(txn_request)
        tx_hash = client.submit_bcs_transaction(signed_txn)
        
        # Wait for confirmation
        client.wait_for_transaction(tx_hash)
        
        print(f"Transfer successful: {amount} APT to {recipient_address}")
        print(f"Transaction hash: {tx_hash}")
        
        return tx_hash
        
    except Exception as e:
        print(f"Transfer failed: {e}")
        return None

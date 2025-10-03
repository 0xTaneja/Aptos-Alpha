import json
import os

from aptos_sdk.account import Account as AptosAccount
from aptos_sdk.async_client import RestClient


def setup(node_url=None, skip_ws=False):
    """Setup Aptos client and account from config"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)
    
    # Create Aptos account from private key
    private_key = config["private_key"]
    account = AptosAccount.load_key(private_key)
    address = config["account_address"]
    
    if address == "":
        address = str(account.address())
    
    print("Running with Aptos account address:", address)
    if address != str(account.address()):
        print("Running with agent address:", str(account.address()))
    
    # Initialize Aptos client
    if node_url is None:
        network = config.get("network", "mainnet")
        if network == "mainnet":
            node_url = "https://fullnode.mainnet.aptoslabs.com/v1"
        else:
            node_url = "https://fullnode.testnet.aptoslabs.com/v1"
    
    client = RestClient(node_url)
    
    # Check account balance
    try:
        account_resources = client.account_resources(address)
        apt_balance = 0
        
        for resource in account_resources:
            if "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>" in resource["type"]:
                apt_balance = float(resource["data"]["coin"]["value"]) / 100000000  # Convert from Octas
                break
        
        if apt_balance == 0:
            print("Not running the example because the provided account has no APT balance.")
            error_string = f"No APT balance:\nIf you think this is a mistake, make sure that {address} has APT on Aptos {network}.\nIf address shown is your API wallet address, update the config to specify the address of your account, not the address of the API wallet."
            raise Exception(error_string)
            
    except Exception as e:
        print(f"Error checking account balance: {e}")
        # Continue anyway for testing
    
    return address, client, account


def setup_multi_account_wallets():
    """Setup multiple Aptos accounts for multi-sig operations"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path) as f:
        config = json.load(f)

    authorized_user_wallets = []
    
    # Handle multi-account configuration
    multi_accounts = config.get("multi_accounts", {}).get("authorized_users", [])
    
    for wallet_config in multi_accounts:
        private_key = wallet_config["private_key"]
        account = AptosAccount.load_key(private_key)
        address = wallet_config["account_address"]
        
        if str(account.address()) != address:
            raise Exception(f"provided authorized user address {address} does not match private key")
        
        print("loaded authorized Aptos user for multi-account", address)
        authorized_user_wallets.append(account)
    
    return authorized_user_wallets


def create_example_config():
    """Create example configuration for Aptos"""
    example_config = {
        "account_address": "",
        "private_key": "",
        "network": "mainnet",
        "vault_address": "",
        "referral_code": "APTOSBOT",
        "telegram": {
            "bot_token": "",
            "allowed_users": [],
            "admin_users": []
        },
        "aptos": {
            "network": "mainnet",
            "node_url": "https://fullnode.mainnet.aptoslabs.com/v1",
            "faucet_url": "https://faucet.testnet.aptoslabs.com"
        },
        "multi_accounts": {
            "authorized_users": [
                {
                    "account_address": "",
                    "private_key": ""
                }
            ]
        }
    }
    
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, 'w') as f:
        json.dump(example_config, f, indent=2)
    
    print(f"Example config created at {config_path}")
    return example_config


def fund_account_testnet(account_address: str, amount: int = 100000000):
    """Fund account on Aptos testnet using faucet"""
    try:
        import requests
        
        faucet_url = "https://faucet.testnet.aptoslabs.com"
        response = requests.post(
            f"{faucet_url}/mint",
            params={
                "address": account_address,
                "amount": amount
            }
        )
        
        if response.status_code == 200:
            print(f"Successfully funded {account_address} with {amount/100000000} APT")
            return True
        else:
            print(f"Failed to fund account: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error funding account: {e}")
        return False


def get_account_info(client: RestClient, address: str):
    """Get Aptos account information"""
    try:
        account_resources = client.account_resources(address)
        account_info = {
            "address": address,
            "resources": len(account_resources),
            "apt_balance": 0,
            "sequence_number": 0
        }
        
        # Get APT balance
        for resource in account_resources:
            if "0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>" in resource["type"]:
                account_info["apt_balance"] = float(resource["data"]["coin"]["value"]) / 100000000
            elif "0x1::account::Account" in resource["type"]:
                account_info["sequence_number"] = int(resource["data"]["sequence_number"])
        
        return account_info
        
    except Exception as e:
        print(f"Error getting account info: {e}")
        return None


def transfer_apt(client: RestClient, sender: AptosAccount, recipient_address: str, amount: int):
    """Transfer APT between accounts"""
    try:
        from aptos_sdk.transactions import EntryFunction, TransactionArgument, TransactionPayload
        from aptos_sdk.bcs import Serializer
        
        # Create transfer transaction
        payload = EntryFunction.natural(
            "0x1::coin",
            "transfer",
            ["0x1::aptos_coin::AptosCoin"],
            [
                TransactionArgument(recipient_address, Serializer.struct),
                TransactionArgument(amount, Serializer.u64),
            ],
        )
        
        # Submit transaction
        txn_hash = client.submit_transaction(sender, TransactionPayload(payload))
        client.wait_for_transaction(txn_hash)
        
        print(f"Successfully transferred {amount/100000000} APT to {recipient_address}")
        return txn_hash
        
    except Exception as e:
        print(f"Error transferring APT: {e}")
        return None
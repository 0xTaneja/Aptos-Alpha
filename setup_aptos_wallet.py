#!/usr/bin/env python3
"""
Production setup script for Aptos wallet
Creates a secure wallet for Aptos Alpha Bot trading operations
"""
import os
import json
import logging
import argparse
import getpass
import time
import asyncio
from pathlib import Path

from aptos_sdk.account import Account
from aptos_auth import AptosAuth
from aptos_utils import create_default_config, fund_from_faucet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("setup_aptos_wallet.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_config(config_path, force=False, network="testnet"):
    """Set up main config file with private key"""
    if os.path.exists(config_path) and not force:
        logger.info(f"Config file {config_path} already exists")
        if input(f"Overwrite existing config file '{config_path}'? (y/n): ").lower() != 'y':
            logger.info(f"Skipping overwrite of {config_path}.")
            return False
    
    print("\n🔐 Aptos Wallet Setup")
    print("=" * 50)
    
    # Option to generate new wallet or use existing
    choice = input("Do you want to:\n1. Generate new wallet\n2. Import existing wallet\nChoice (1/2): ").strip()
    
    if choice == "1":
        # Generate new wallet
        account = Account.generate()
        private_key = f"0x{account.private_key.hex()}"
        address = str(account.address())
        
        print(f"\n✅ New Aptos wallet generated!")
        print(f"Address: {address}")
        print(f"Private Key: {private_key}")
        print("\n⚠️  IMPORTANT: Save your private key securely!")
        print("⚠️  Never share your private key with anyone!")
        
    elif choice == "2":
        # Import existing wallet
        private_key = ""
        while not private_key:
            private_key = getpass.getpass("Enter your Aptos private key (64 hex chars, optionally starting with 0x): ")
            if not private_key:
                logger.warning("Private key cannot be empty.")
                if input("Try again? (y/n): ").lower() != 'y':
                    return False
        
        # Validate format
        if private_key.startswith("0x"):
            hex_key = private_key[2:]
        else:
            hex_key = private_key
            private_key = f"0x{private_key}"
        
        if len(hex_key) != 64:
            logger.error("Invalid private key format. Must be 64 hex characters.")
            return False
        
        try:
            account = Account.load_key(hex_key)
            address = str(account.address())
            print(f"\n✅ Wallet imported successfully!")
            print(f"Address: {address}")
        except Exception as e:
            logger.error(f"Invalid private key: {e}")
            return False
    else:
        logger.error("Invalid choice")
        return False
    
    # Get account address (optional override)
    account_address = input(f"\nAccount address (press Enter to use derived address {address}): ").strip()
    if not account_address:
        account_address = address
    
    # Create configuration
    config = create_default_config(
        private_key=private_key,
        network=network,
        config_path=config_path
    )
    
    # Update with account address if different
    if account_address != address:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        config_data['aptos']['account_address'] = account_address
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    print(f"\n✅ Configuration saved to: {config_path}")
    return True

def setup_wallet_config(wallet_config_path, force=False, network="testnet"):
    """Set up wallet-specific config file"""
    if os.path.exists(wallet_config_path) and not force:
        logger.info(f"Wallet config file {wallet_config_path} already exists")
        if input(f"Overwrite existing wallet config '{wallet_config_path}'? (y/n): ").lower() != 'y':
            logger.info(f"Skipping overwrite of {wallet_config_path}.")
            return False
    
    print("\n🏦 Wallet Configuration Setup")
    print("=" * 50)
    
    # Generate or import wallet
    choice = input("Generate new wallet for this config? (y/n): ").lower()
    
    if choice == 'y':
        account = Account.generate()
        private_key = f"0x{account.private_key.hex()}"
        address = str(account.address())
        
        print(f"\n✅ New wallet generated for config!")
        print(f"Address: {address}")
        print(f"Private Key: {private_key}")
        
    else:
        private_key = getpass.getpass("Enter private key for wallet config: ")
        if private_key.startswith("0x"):
            hex_key = private_key[2:]
        else:
            hex_key = private_key
            private_key = f"0x{private_key}"
        
        try:
            account = Account.load_key(hex_key)
            address = str(account.address())
        except Exception as e:
            logger.error(f"Invalid private key: {e}")
            return False
    
    # Create wallet config
    wallet_config = {
        "address": address,
        "private_key": private_key,
        "public_key": f"0x{account.public_key.hex()}",
        "network": network,
        "created_at": int(time.time()),
        "wallet_type": "trading_wallet"
    }
    
    with open(wallet_config_path, 'w') as f:
        json.dump(wallet_config, f, indent=2)
    
    print(f"✅ Wallet config saved to: {wallet_config_path}")
    return True

async def test_connection(config_path, network="testnet"):
    """Test connection with the configured wallet"""
    try:
        print("\n🔍 Testing Aptos connection...")
        
        # Initialize auth
        auth = AptosAuth(
            config_dir=os.path.dirname(config_path) or ".",
            network=network
        )
        
        # Connect
        address, info, exchange = await auth.connect()
        
        print(f"✅ Connection successful!")
        print(f"Address: {address}")
        print(f"Network: {network}")
        
        # Get balance
        balance = await info.get_account_balance(address)
        print(f"Balance: {balance / 100000000:.8f} APT")
        
        # Get portfolio
        portfolio = await info.get_account_portfolio(address)
        if portfolio.get("total_value_usd"):
            print(f"Portfolio Value: ${portfolio['total_value_usd']:.2f}")
        
        # Fund from faucet if testnet and balance is low
        if network == "testnet" and balance < 100000000:  # Less than 1 APT
            print("\n💰 Low balance detected. Attempting to fund from faucet...")
            success = await fund_from_faucet(address)
            if success:
                print("✅ Faucet funding successful!")
                # Check new balance
                await asyncio.sleep(5)
                new_balance = await info.get_account_balance(address)
                print(f"New balance: {new_balance / 100000000:.8f} APT")
            else:
                print("❌ Faucet funding failed. You may need to fund manually.")
                print(f"Visit: https://faucet.testnet.aptoslabs.com")
                print(f"Address: {address}")
        
        await auth.close()
        return True
        
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False

def setup_telegram_config(config_path):
    """Setup Telegram bot configuration"""
    print("\n🤖 Telegram Bot Setup")
    print("=" * 50)
    
    bot_token = input("Enter your Telegram bot token (from @BotFather): ").strip()
    if not bot_token:
        print("⚠️ No bot token provided. You can add it later to the config file.")
        return
    
    bot_username = input("Enter your bot username (optional): ").strip()
    
    # Get admin users
    admin_users = []
    print("\nEnter admin user IDs (press Enter when done):")
    while True:
        user_id = input("Admin user ID: ").strip()
        if not user_id:
            break
        try:
            admin_users.append(int(user_id))
        except ValueError:
            print("Invalid user ID. Please enter a number.")
    
    # Update config file
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        config['telegram_bot']['bot_token'] = bot_token
        if bot_username:
            config['telegram_bot']['bot_username'] = bot_username
        if admin_users:
            config['telegram_bot']['admin_users'] = admin_users
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("✅ Telegram configuration updated!")
        
    except Exception as e:
        logger.error(f"Failed to update Telegram config: {e}")

def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(description="Setup Aptos Alpha Bot wallet")
    parser.add_argument("--config", default="config.json", help="Main config file path")
    parser.add_argument("--wallet-config", default="wallet_config.json", help="Wallet config file path")
    parser.add_argument("--network", choices=["testnet", "mainnet"], default="testnet", help="Aptos network")
    parser.add_argument("--force", action="store_true", help="Overwrite existing config files")
    parser.add_argument("--test-only", action="store_true", help="Only test existing configuration")
    parser.add_argument("--telegram", action="store_true", help="Setup Telegram bot configuration")
    
    args = parser.parse_args()
    
    print("🚀 Aptos Alpha Bot Wallet Setup")
    print("=" * 50)
    print(f"Network: {args.network.upper()}")
    print(f"Config file: {args.config}")
    print(f"Wallet config: {args.wallet_config}")
    
    if args.test_only:
        # Test existing configuration
        if not os.path.exists(args.config):
            logger.error(f"Config file {args.config} not found")
            return
        
        asyncio.run(test_connection(args.config, args.network))
        return
    
    try:
        # Setup main config
        if not setup_config(args.config, args.force, args.network):
            logger.error("Main config setup failed")
            return
        
        # Setup wallet config
        if not setup_wallet_config(args.wallet_config, args.force, args.network):
            logger.error("Wallet config setup failed")
            return
        
        # Setup Telegram if requested
        if args.telegram:
            setup_telegram_config(args.config)
        
        # Test connection
        print("\n" + "=" * 50)
        success = asyncio.run(test_connection(args.config, args.network))
        
        if success:
            print("\n🎉 Setup completed successfully!")
            print("\nNext steps:")
            print("1. Review your configuration files")
            print("2. Add your Telegram bot token if not done already")
            print("3. Run the bot with: python main.py")
            
            if args.network == "testnet":
                print("\n💡 Testnet Tips:")
                print("• Use the faucet to get test APT: https://faucet.testnet.aptoslabs.com")
                print("• Test all features before moving to mainnet")
            else:
                print("\n⚠️  Mainnet Warning:")
                print("• Double-check all configurations")
                print("• Start with small amounts")
                print("• Monitor the bot closely")
        else:
            print("\n❌ Setup completed but connection test failed")
            print("Please check your configuration and try again")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup interrupted by user")
    except Exception as e:
        logger.error(f"Setup failed: {e}")

if __name__ == "__main__":
    main()

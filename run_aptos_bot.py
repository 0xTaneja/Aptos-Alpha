"""
Quick start script for the Aptos Alpha Trading Bot
This script ensures everything is properly configured and starts the bot
"""

import asyncio
import json
import os
import sys
from pathlib import Path

async def main():
    """Main startup with all checks"""
    print("🚀 APTOS ALPHA BOT STARTUP")
    print("=" * 50)
    
    # Check configuration
    config_path = Path("config.json")
    if not config_path.exists():
        print("❌ config.json not found!")
        print("💡 Run 'python quick_start_aptos.py' first to create configuration")
        return
    
    # Load and check config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Check Telegram token
    bot_token = config.get('telegram_bot', {}).get('bot_token', '')
    if bot_token in ['', 'GET_TOKEN_FROM_BOTFATHER']:
        print("❌ Telegram bot token not configured!")
        print("💡 Get token from @BotFather and update config.json")
        return
    
    # Check Aptos configuration
    aptos_config = config.get('aptos', {})
    private_key = aptos_config.get('admin_private_key', '')
    
    if not private_key:
        print("❌ Aptos private key not configured!")
        print("💡 Run 'python setup_aptos_wallet.py' to configure wallet")
        return
    
    # Check network configuration
    network = config.get('general', {}).get('environment', 'testnet')
    node_url = config.get('general', {}).get('node_url', '')
    
    if not node_url:
        print("❌ Aptos node URL not configured!")
        return
    
    print("✅ Configuration checks passed")
    print(f"Network: {network.upper()}")
    print(f"Node URL: {node_url}")
    
    print("\n🔧 Starting Aptos connection test...")
    
    # Test Aptos connection
    try:
        from aptos_auth import AptosAuth
        
        auth = AptosAuth(network=network)
        address, info, exchange = await auth.connect()
        
        print(f"✅ Aptos connection successful!")
        print(f"Address: {address}")
        
        # Get balance
        balance = await info.get_account_balance(address)
        print(f"Balance: {balance / 100000000:.8f} APT")
        
        await auth.close()
        
    except Exception as e:
        print(f"❌ Aptos connection test failed: {e}")
        print("💡 Check your private key and network configuration")
        return
    
    print("\n🧪 Running database initialization test...")
    
    # Test database
    try:
        from database import DatabaseManager
        
        db = DatabaseManager()
        await db.initialize()
        print("✅ Database initialization successful!")
        await db.close()
        
    except Exception as e:
        print(f"⚠️ Database test failed: {e}")
        print("💡 Database will be created automatically on first run")
    
    print("\n🚀 Starting main bot...")
    
    # Choose which bot to run
    print("Choose bot to run:")
    print("1. Main bot (main.py) - Full system")
    print("2. Complete bot (complete_aptos_bot.py) - Standalone")
    
    choice = input("Enter choice (1/2, default=1): ").strip() or "1"
    
    # Start the selected bot
    try:
        if choice == "2":
            print("Starting Complete Aptos Bot...")
            from complete_aptos_bot import main as bot_main
            await bot_main()
        else:
            print("Starting Main Aptos Bot...")
            from main import main as bot_main
            await bot_main()
            
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot startup failed: {e}")
        print("💡 Check the error messages above and ensure all configuration is correct")
        
        # Provide helpful debugging info
        print("\n🔍 DEBUGGING HELP:")
        print("1. Check config.json has valid bot_token and private_key")
        print("2. Ensure Aptos account has sufficient balance")
        print("3. Verify network connectivity")
        print("4. Check logs for detailed error messages")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutdown complete")
    except Exception as e:
        print(f"💥 Critical error: {e}")
        sys.exit(1)

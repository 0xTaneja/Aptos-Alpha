#!/usr/bin/env python3
"""
Test script to verify the migration is working
"""

import sys
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_imports():
    """Test that all imports work"""
    print("🔧 Testing imports...")
    
    try:
        from database import DatabaseManager
        print("✅ Database import: OK")
    except Exception as e:
        print(f"❌ Database import failed: {e}")
        return False
    
    try:
        from telegram_bot.aptos_bot import TelegramTradingBot
        print("✅ Telegram bot import: OK")
    except Exception as e:
        print(f"❌ Telegram bot import failed: {e}")
        return False
    
    try:
        from config import ConfigManager
        print("✅ Config import: OK")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    return True

def test_basic_functionality():
    """Test basic functionality without Aptos SDK"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        # Test database
        from database import DatabaseManager
        db = DatabaseManager("test.db")
        print("✅ Database creation: OK")
        
        # Test config
        from config import ConfigManager
        config_manager = ConfigManager()
        print("✅ Config manager creation: OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 APTOS ALPHA BOT - MIGRATION TEST")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed!")
        return False
    
    # Test basic functionality
    if not test_basic_functionality():
        print("\n❌ Functionality tests failed!")
        return False
    
    print("\n✅ ALL TESTS PASSED!")
    print("🎯 Migration structure is working correctly")
    print("\n📋 NEXT STEPS:")
    print("1. Install Aptos SDK properly")
    print("2. Configure Telegram bot token")
    print("3. Deploy Move contracts")
    print("4. Test full functionality")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

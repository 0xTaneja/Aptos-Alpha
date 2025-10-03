"""
Configuration management for Aptos Alpha Bot
"""

import os
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class AptosConfig:
    """Aptos network configuration"""
    node_url: str
    faucet_url: str
    contract_address: str
    admin_private_key: Optional[str] = None
    testnet_mode: bool = True

@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str
    admin_users: List[int]
    webhook_url: Optional[str] = None

@dataclass
class TradingConfig:
    """Trading parameters configuration"""
    minimum_deposit: int = 50000000  # 0.5 APT
    performance_fee_bps: int = 1000  # 10%
    lockup_period: int = 86400  # 1 day
    default_grid_spacing: int = 200  # 2%
    default_grid_levels: int = 10
    default_amount_per_level: int = 10000000  # 0.1 APT

@dataclass
class BotConfig:
    """Main bot configuration"""
    aptos: AptosConfig
    telegram: TelegramConfig
    trading: TradingConfig
    database_url: str = "sqlite:///aptos_alpha_bot.db"
    log_level: str = "INFO"
    debug_mode: bool = False

def load_config() -> BotConfig:
    """Load configuration from environment variables"""
    
    # Aptos configuration
    aptos_config = AptosConfig(
        node_url=os.getenv("APTOS_NODE_URL", "https://fullnode.testnet.aptoslabs.com/v1"),
        faucet_url=os.getenv("APTOS_FAUCET_URL", "https://faucet.testnet.aptoslabs.com"),
        contract_address=os.getenv("CONTRACT_ADDRESS", "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69"),
        admin_private_key=os.getenv("ADMIN_PRIVATE_KEY"),
        testnet_mode=os.getenv("TESTNET_MODE", "true").lower() == "true"
    )
    
    # Telegram configuration
    admin_users_str = os.getenv("TELEGRAM_ADMIN_USERS", "")
    admin_users = [int(x.strip()) for x in admin_users_str.split(",") if x.strip().isdigit()]
    
    telegram_config = TelegramConfig(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        admin_users=admin_users,
        webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL")
    )
    
    # Trading configuration
    trading_config = TradingConfig(
        minimum_deposit=int(os.getenv("MINIMUM_DEPOSIT", "50000000")),
        performance_fee_bps=int(os.getenv("PERFORMANCE_FEE_BPS", "1000")),
        lockup_period=int(os.getenv("LOCKUP_PERIOD", "86400")),
        default_grid_spacing=int(os.getenv("DEFAULT_GRID_SPACING", "200")),
        default_grid_levels=int(os.getenv("DEFAULT_GRID_LEVELS", "10")),
        default_amount_per_level=int(os.getenv("DEFAULT_AMOUNT_PER_LEVEL", "10000000"))
    )
    
    return BotConfig(
        aptos=aptos_config,
        telegram=telegram_config,
        trading=trading_config,
        database_url=os.getenv("DATABASE_URL", "sqlite:///aptos_alpha_bot.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true"
    )

# Global config instance
config = load_config()

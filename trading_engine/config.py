from dataclasses import dataclass, field
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class TradingConfig:
    """Trading configuration for Aptos-based trading operations"""
    # Aptos network gas and fee structure
    base_gas_unit_price: int = 100       # Base gas price in octas per unit
    max_gas_amount: int = 10000          # Maximum gas per transaction
    transaction_timeout: int = 30        # Transaction timeout in seconds
    
    # Trading fees (DEX-specific)
    dex_swap_fee: float = 0.003          # 0.3% swap fee (typical for AMM DEXs)
    liquidity_provider_fee: float = 0.0025  # 0.25% LP fee
    protocol_fee: float = 0.0005         # 0.05% protocol fee
    
    # Volume-based fee discounts
    tier_1_volume: float = 1000          # 1000 APT volume threshold
    tier_2_volume: float = 5000          # 5000 APT volume threshold  
    tier_3_volume: float = 25000         # 25000 APT volume threshold
    
    tier_1_discount: float = 0.1         # 10% fee discount
    tier_2_discount: float = 0.2         # 20% fee discount
    tier_3_discount: float = 0.3         # 30% fee discount
    
    # Risk management
    max_position_size: float = 1000      # 1000 APT max position
    min_profit_threshold: float = 0.005  # 0.5% minimum profit
    max_slippage: float = 0.05           # 5% maximum slippage
    
    # Vault settings
    vault_profit_share: float = 0.15     # 15% profit share for vault managers
    vault_minimum_deposit: float = 10    # 10 APT minimum deposit
    vault_withdrawal_fee: float = 0.001  # 0.1% withdrawal fee
    vault_performance_fee: float = 0.2   # 20% performance fee
    
    # Staking and rewards
    staking_reward_rate: float = 0.07    # 7% APY for staking
    delegation_commission: float = 0.1   # 10% validator commission
    min_stake_amount: float = 11         # 11 APT minimum stake (Aptos requirement)

    # Trading settings
    max_position_size_usd: float = 10000.0
    default_slippage_pct: float = 0.005  # 0.5%
    risk_level: str = "medium"  # e.g., "low", "medium", "high"
    
    # Aptos-specific strategy configurations
    grid_trading_config: Dict[str, any] = field(default_factory=lambda: {
        "levels": 10,
        "spacing_pct": 0.005,  # 0.5% spacing between grid levels
        "enabled": True,
        "default_pair": "APT-USDC",
        "min_order_size": 0.1,  # 0.1 APT minimum
        "max_spread": 0.1       # 10% maximum spread
    })
    
    dca_config: Dict[str, any] = field(default_factory=lambda: {
        "amount_per_buy_apt": 10.0,    # 10 APT per DCA buy
        "interval_hours": 24,          # Buy every 24 hours
        "enabled": False,
        "default_pair": "APT-USDC",
        "max_price_impact": 0.02       # 2% maximum price impact
    })
    
    # Aptos network configuration
    network_config: Dict[str, any] = field(default_factory=lambda: {
        "node_url": "https://fullnode.mainnet.aptoslabs.com/v1",
        "faucet_url": "https://faucet.testnet.aptoslabs.com",
        "chain_id": 1,  # Mainnet
        "indexer_url": "https://indexer.mainnet.aptoslabs.com/v1/graphql"
    })
    
    # DEX contract addresses
    dex_contracts: Dict[str, str] = field(default_factory=lambda: {
        "pancakeswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",
        "thala": "0x48271d39d0b05bd6efca2278f22277d6fcc375504f9839fd73f74ace240861af",
        "liquidswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12",
        "aptoswap": "0x190d44266241744264b964a37b8f09863167a12d3e70cda39376cfb4e3561e12"
    })

    def __post_init__(self):
        """Validate Aptos trading configuration"""
        # Validate risk level
        if self.risk_level not in ["low", "medium", "high"]:
            raise ValueError("Invalid risk level specified in TradingConfig. Must be 'low', 'medium', or 'high'.")
        
        # Validate slippage
        if not 0 < self.default_slippage_pct < 0.1:
            logger.warning(f"Default slippage {self.default_slippage_pct*100}% is unusual. Ensure this is intended.")
        
        # Validate gas settings
        if self.base_gas_unit_price < 1:
            logger.warning("Gas unit price is very low, transactions may fail.")
        
        # Validate APT amounts
        if self.min_stake_amount < 11:
            logger.warning("Minimum stake amount is below Aptos requirement of 11 APT.")
        
        # Validate fee structure
        if self.dex_swap_fee > 0.01:  # 1%
            logger.warning(f"DEX swap fee {self.dex_swap_fee*100}% seems high.")
        
        # Validate network configuration
        network_config = self.network_config
        if not network_config.get("node_url", "").startswith("https://"):
            logger.warning("Node URL should use HTTPS for security.")
        
        logger.info("Aptos trading configuration validated successfully.")

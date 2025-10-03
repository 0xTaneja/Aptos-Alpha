"""
Merkle Trade Integration - Perpetuals & Derivatives Trading
https://github.com/merkle-trade/merkle-ts-sdk

Adds leveraged perpetual futures trading capabilities to the bot
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

class MerklePerpetuals:
    """
    Merkle Trade Perpetuals Integration
    Enables leveraged trading up to 100x on Aptos
    """
    
    # Merkle contract addresses on Aptos (adjust based on actual deployment)
    MERKLE_PERP_CONTRACT = "0x..."  # Main perpetuals contract
    MERKLE_ORACLE = "0x..."  # Price oracle
    
    # Supported leverage levels
    MAX_LEVERAGE = 100
    MIN_LEVERAGE = 1
    
    # Supported symbols
    SUPPORTED_SYMBOLS = [
        "APT-PERP",
        "BTC-PERP",
        "ETH-PERP",
        "SOL-PERP",
        "SUI-PERP"
    ]
    
    def __init__(self, aptos_client, account):
        """
        Initialize Merkle Perpetuals
        
        Args:
            aptos_client: RestClient instance
            account: User's Aptos account
        """
        self.client = aptos_client
        self.account = account
        self.positions = {}  # Track open positions
        
        logger.info("Initialized Merkle Perpetuals integration")
    
    async def get_market_info(self, symbol: str) -> Dict:
        """
        Get perpetual market information
        
        Args:
            symbol: Market symbol (e.g., "APT-PERP")
            
        Returns:
            Market data including price, funding rate, open interest
        """
        try:
            if symbol not in self.SUPPORTED_SYMBOLS:
                return {"success": False, "error": f"Unsupported symbol: {symbol}"}
            
            # Query Merkle contract for market data
            # In production, this would call the actual Merkle SDK
            market_data = {
                "success": True,
                "symbol": symbol,
                "mark_price": 0.0,  # Current mark price
                "index_price": 0.0,  # Index price
                "funding_rate": 0.0,  # Current funding rate
                "next_funding": 0,  # Next funding timestamp
                "open_interest": 0.0,  # Total open interest
                "24h_volume": 0.0,  # 24h trading volume
                "max_leverage": self.MAX_LEVERAGE,
                "min_size": 0.01,  # Minimum position size
                "maker_fee": 0.02,  # 0.02% maker fee
                "taker_fee": 0.06,  # 0.06% taker fee
            }
            
            logger.info(f"Market info for {symbol}: Price={market_data['mark_price']}, Funding={market_data['funding_rate']}%")
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market info: {e}")
            return {"success": False, "error": str(e)}
    
    async def open_position(
        self,
        symbol: str,
        size: float,
        leverage: int,
        is_long: bool,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Open a leveraged perpetual position
        
        Args:
            symbol: Market symbol (e.g., "APT-PERP")
            size: Position size in base currency
            leverage: Leverage multiplier (1-100)
            is_long: True for long, False for short
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            
        Returns:
            Position details including entry price, liquidation price
        """
        try:
            # Validate inputs
            if symbol not in self.SUPPORTED_SYMBOLS:
                return {"success": False, "error": f"Unsupported symbol: {symbol}"}
            
            if leverage < self.MIN_LEVERAGE or leverage > self.MAX_LEVERAGE:
                return {"success": False, "error": f"Leverage must be between {self.MIN_LEVERAGE}-{self.MAX_LEVERAGE}"}
            
            if size <= 0:
                return {"success": False, "error": "Size must be positive"}
            
            # Get current market price
            market = await self.get_market_info(symbol)
            if not market.get("success"):
                return market
            
            entry_price = market["mark_price"]
            
            # Calculate position details
            collateral = size * entry_price / leverage
            position_value = size * entry_price
            
            # Calculate liquidation price
            # For long: liq_price = entry * (1 - 1/leverage + maintenance_margin)
            # For short: liq_price = entry * (1 + 1/leverage - maintenance_margin)
            maintenance_margin = 0.005  # 0.5%
            if is_long:
                liquidation_price = entry_price * (1 - 1/leverage + maintenance_margin)
            else:
                liquidation_price = entry_price * (1 + 1/leverage - maintenance_margin)
            
            # In production, this would submit transaction to Merkle contract
            position_id = f"merkle_{symbol}_{int(asyncio.get_event_loop().time())}"
            
            position = {
                "success": True,
                "position_id": position_id,
                "symbol": symbol,
                "side": "LONG" if is_long else "SHORT",
                "size": size,
                "leverage": leverage,
                "entry_price": entry_price,
                "liquidation_price": liquidation_price,
                "collateral": collateral,
                "position_value": position_value,
                "unrealized_pnl": 0.0,
                "funding_paid": 0.0,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Store position
            self.positions[position_id] = position
            
            logger.info(f"Opened {position['side']} position: {size} {symbol} @{entry_price} with {leverage}x leverage")
            logger.info(f"Liquidation price: {liquidation_price}")
            
            return position
            
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return {"success": False, "error": str(e)}
    
    async def close_position(self, position_id: str, partial_size: Optional[float] = None) -> Dict:
        """
        Close a perpetual position (fully or partially)
        
        Args:
            position_id: Position ID to close
            partial_size: Optional partial size to close (None = close all)
            
        Returns:
            Closing details including realized PnL
        """
        try:
            if position_id not in self.positions:
                return {"success": False, "error": "Position not found"}
            
            position = self.positions[position_id]
            
            # Get current market price
            market = await self.get_market_info(position["symbol"])
            if not market.get("success"):
                return market
            
            exit_price = market["mark_price"]
            
            # Calculate size to close
            close_size = partial_size if partial_size else position["size"]
            if close_size > position["size"]:
                return {"success": False, "error": "Close size exceeds position size"}
            
            # Calculate realized PnL
            if position["side"] == "LONG":
                pnl = (exit_price - position["entry_price"]) * close_size
            else:
                pnl = (position["entry_price"] - exit_price) * close_size
            
            # Account for leverage
            pnl_percentage = (pnl / (position["collateral"] * close_size / position["size"])) * 100
            
            # Calculate fees
            taker_fee = close_size * exit_price * 0.0006  # 0.06% taker fee
            net_pnl = pnl - taker_fee
            
            result = {
                "success": True,
                "position_id": position_id,
                "symbol": position["symbol"],
                "side": position["side"],
                "closed_size": close_size,
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "realized_pnl": net_pnl,
                "pnl_percentage": pnl_percentage,
                "fees_paid": taker_fee,
                "funding_paid": position.get("funding_paid", 0)
            }
            
            # Update or remove position
            if close_size >= position["size"]:
                del self.positions[position_id]
                logger.info(f"Closed position {position_id}: PnL = {net_pnl:.2f} ({pnl_percentage:.2f}%)")
            else:
                position["size"] -= close_size
                position["collateral"] *= (position["size"] / (position["size"] + close_size))
                logger.info(f"Partially closed position {position_id}: {close_size} of {position['size'] + close_size}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_position(self, position_id: str) -> Dict:
        """Get details of an open position with current PnL"""
        try:
            if position_id not in self.positions:
                return {"success": False, "error": "Position not found"}
            
            position = self.positions[position_id].copy()
            
            # Get current market price
            market = await self.get_market_info(position["symbol"])
            if market.get("success"):
                current_price = market["mark_price"]
                
                # Calculate unrealized PnL
                if position["side"] == "LONG":
                    unrealized_pnl = (current_price - position["entry_price"]) * position["size"]
                else:
                    unrealized_pnl = (position["entry_price"] - current_price) * position["size"]
                
                position["current_price"] = current_price
                position["unrealized_pnl"] = unrealized_pnl
                position["unrealized_pnl_percentage"] = (unrealized_pnl / position["collateral"]) * 100
            
            position["success"] = True
            return position
            
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_all_positions(self) -> List[Dict]:
        """Get all open positions with current PnL"""
        positions = []
        for position_id in list(self.positions.keys()):
            pos = await self.get_position(position_id)
            if pos.get("success"):
                positions.append(pos)
        return positions
    
    async def update_stop_loss(self, position_id: str, stop_loss: float) -> Dict:
        """Update stop loss for a position"""
        try:
            if position_id not in self.positions:
                return {"success": False, "error": "Position not found"}
            
            self.positions[position_id]["stop_loss"] = stop_loss
            logger.info(f"Updated stop loss for {position_id} to {stop_loss}")
            
            return {"success": True, "position_id": position_id, "stop_loss": stop_loss}
            
        except Exception as e:
            logger.error(f"Error updating stop loss: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_take_profit(self, position_id: str, take_profit: float) -> Dict:
        """Update take profit for a position"""
        try:
            if position_id not in self.positions:
                return {"success": False, "error": "Position not found"}
            
            self.positions[position_id]["take_profit"] = take_profit
            logger.info(f"Updated take profit for {position_id} to {take_profit}")
            
            return {"success": True, "position_id": position_id, "take_profit": take_profit}
            
        except Exception as e:
            logger.error(f"Error updating take profit: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_funding_rate(self, symbol: str) -> Dict:
        """Get current funding rate for a symbol"""
        market = await self.get_market_info(symbol)
        if market.get("success"):
            return {
                "success": True,
                "symbol": symbol,
                "funding_rate": market["funding_rate"],
                "next_funding": market["next_funding"]
            }
        return market
    
    async def calculate_liquidation_price(
        self,
        entry_price: float,
        leverage: int,
        is_long: bool
    ) -> float:
        """Calculate liquidation price for given parameters"""
        maintenance_margin = 0.005  # 0.5%
        if is_long:
            return entry_price * (1 - 1/leverage + maintenance_margin)
        else:
            return entry_price * (1 + 1/leverage - maintenance_margin)
    
    async def get_account_margin(self) -> Dict:
        """Get account margin and collateral information"""
        try:
            total_collateral = sum(pos["collateral"] for pos in self.positions.values())
            total_position_value = sum(pos["position_value"] for pos in self.positions.values())
            
            # Calculate total unrealized PnL
            total_unrealized_pnl = 0.0
            for position_id in self.positions:
                pos = await self.get_position(position_id)
                if pos.get("success"):
                    total_unrealized_pnl += pos.get("unrealized_pnl", 0)
            
            available_balance = 0.0  # Would query from account in production
            total_equity = available_balance + total_collateral + total_unrealized_pnl
            
            return {
                "success": True,
                "total_equity": total_equity,
                "total_collateral": total_collateral,
                "available_balance": available_balance,
                "total_position_value": total_position_value,
                "unrealized_pnl": total_unrealized_pnl,
                "margin_ratio": (total_equity / total_position_value * 100) if total_position_value > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting account margin: {e}")
            return {"success": False, "error": str(e)}

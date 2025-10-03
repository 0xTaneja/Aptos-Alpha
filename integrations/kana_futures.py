"""
Kana Labs Perpetual Futures Integration
https://docs.kanalabs.io/perpetual-futures/kana-perps/api-docs

Adds alternative perpetuals venue and funding rate arbitrage
"""

import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class KanaFutures:
    """
    Kana Labs Perpetual Futures Integration
    Provides alternative perps venue and funding arbitrage opportunities
    """
    
    # Kana API endpoints
    KANA_API = "https://api.kanalabs.io/perps/v1"
    
    # Supported markets
    SUPPORTED_MARKETS = [
        "APT-PERP",
        "BTC-PERP",
        "ETH-PERP",
        "SOL-PERP"
    ]
    
    def __init__(self, aptos_account=None):
        """
        Initialize Kana Futures
        
        Args:
            aptos_account: User's Aptos account for signing
        """
        self.account = aptos_account
        self.session = None
        self.positions = {}
        
        logger.info("Initialized Kana Labs Futures integration")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_markets(self) -> List[Dict]:
        """Get all available perpetual markets"""
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/markets"
            
            async with session.get(url) as response:
                if response.status == 200:
                    markets = await response.json()
                    logger.info(f"Retrieved {len(markets)} Kana markets")
                    return markets
                return []
                
        except Exception as e:
            logger.error(f"Error getting markets: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Dict:
        """
        Get current and predicted funding rates
        
        Args:
            symbol: Market symbol (e.g., "APT-PERP")
            
        Returns:
            Funding rate data including current, predicted, and history
        """
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/funding"
            params = {"symbol": symbol}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    funding_data = await response.json()
                    
                    return {
                        "success": True,
                        "symbol": symbol,
                        "current_rate": funding_data.get("current_rate", 0),
                        "predicted_rate": funding_data.get("predicted_rate", 0),
                        "next_funding_time": funding_data.get("next_funding_time"),
                        "funding_interval": funding_data.get("funding_interval", 8),  # hours
                        "8h_rate": funding_data.get("rate_8h", 0),
                        "24h_avg": funding_data.get("rate_24h_avg", 0)
                    }
                    
                return {"success": False, "error": f"HTTP {response.status}"}
                
        except Exception as e:
            logger.error(f"Error getting funding rate: {e}")
            return {"success": False, "error": str(e)}
    
    async def find_funding_arbitrage(self, threshold: float = 0.01) -> List[Dict]:
        """
        Find funding rate arbitrage opportunities across venues
        
        Args:
            threshold: Minimum rate difference to report (default 1%)
            
        Returns:
            List of arbitrage opportunities with rate differences
        """
        opportunities = []
        
        try:
            for symbol in self.SUPPORTED_MARKETS:
                kana_funding = await self.get_funding_rate(symbol)
                
                if not kana_funding.get("success"):
                    continue
                
                kana_rate = kana_funding["current_rate"]
                
                # In production, compare with Merkle Trade funding rates
                # For now, flag any high/low rates
                if abs(kana_rate) > threshold:
                    opportunities.append({
                        "symbol": symbol,
                        "kana_rate": kana_rate,
                        "annual_yield": kana_rate * 365 * 3,  # 8h funding * 3 per day
                        "strategy": "short" if kana_rate > 0 else "long",
                        "expected_return": abs(kana_rate) * 100
                    })
            
            # Sort by potential return
            opportunities.sort(key=lambda x: abs(x["kana_rate"]), reverse=True)
            
            logger.info(f"Found {len(opportunities)} funding arbitrage opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error finding arbitrage: {e}")
            return []
    
    async def get_orderbook(self, symbol: str, depth: int = 10) -> Dict:
        """
        Get orderbook for a market
        
        Args:
            symbol: Market symbol
            depth: Orderbook depth (number of levels)
            
        Returns:
            Orderbook with bids and asks
        """
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/orderbook/{symbol}"
            params = {"depth": depth}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    orderbook = await response.json()
                    
                    return {
                        "success": True,
                        "symbol": symbol,
                        "bids": orderbook.get("bids", []),
                        "asks": orderbook.get("asks", []),
                        "timestamp": orderbook.get("timestamp")
                    }
                    
                return {"success": False, "error": f"HTTP {response.status}"}
                
        except Exception as e:
            logger.error(f"Error getting orderbook: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_market_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent market trades"""
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/trades/{symbol}"
            params = {"limit": limit}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    trades = await response.json()
                    return trades
                return []
                
        except Exception as e:
            logger.error(f"Error getting market trades: {e}")
            return []
    
    async def open_position(
        self,
        symbol: str,
        size: float,
        leverage: int,
        is_long: bool,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None
    ) -> Dict:
        """
        Open perpetual position on Kana Labs
        
        Args:
            symbol: Market symbol
            size: Position size
            leverage: Leverage (1-50x on Kana)
            is_long: True for long, False for short
            order_type: "MARKET" or "LIMIT"
            limit_price: Price for limit orders
            
        Returns:
            Position details
        """
        try:
            if symbol not in self.SUPPORTED_MARKETS:
                return {"success": False, "error": f"Unsupported market: {symbol}"}
            
            if leverage < 1 or leverage > 50:
                return {"success": False, "error": "Leverage must be 1-50x"}
            
            session = await self._get_session()
            url = f"{self.KANA_API}/positions"
            
            payload = {
                "symbol": symbol,
                "size": size,
                "leverage": leverage,
                "side": "LONG" if is_long else "SHORT",
                "order_type": order_type,
                "limit_price": limit_price
            }
            
            # In production, sign with Aptos account
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    position_id = result.get("position_id")
                    self.positions[position_id] = result
                    
                    logger.info(f"Opened Kana position: {size} {symbol} {leverage}x {'LONG' if is_long else 'SHORT'}")
                    
                    return {
                        "success": True,
                        "position_id": position_id,
                        "symbol": symbol,
                        "size": size,
                        "leverage": leverage,
                        "side": "LONG" if is_long else "SHORT",
                        "entry_price": result.get("entry_price"),
                        "liquidation_price": result.get("liquidation_price"),
                        "collateral": result.get("collateral")
                    }
                    
                return {"success": False, "error": f"HTTP {response.status}"}
                
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return {"success": False, "error": str(e)}
    
    async def close_position(self, position_id: str) -> Dict:
        """Close a Kana perpetual position"""
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/positions/{position_id}/close"
            
            async with session.post(url) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if position_id in self.positions:
                        del self.positions[position_id]
                    
                    logger.info(f"Closed Kana position {position_id}: PnL = {result.get('realized_pnl')}")
                    
                    return {
                        "success": True,
                        "position_id": position_id,
                        "realized_pnl": result.get("realized_pnl"),
                        "exit_price": result.get("exit_price"),
                        "fees": result.get("fees")
                    }
                    
                return {"success": False, "error": f"HTTP {response.status}"}
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_position(self, position_id: str) -> Dict:
        """Get current position details with unrealized PnL"""
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/positions/{position_id}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    position = await response.json()
                    
                    return {
                        "success": True,
                        "position_id": position_id,
                        "symbol": position.get("symbol"),
                        "size": position.get("size"),
                        "leverage": position.get("leverage"),
                        "side": position.get("side"),
                        "entry_price": position.get("entry_price"),
                        "current_price": position.get("mark_price"),
                        "liquidation_price": position.get("liquidation_price"),
                        "unrealized_pnl": position.get("unrealized_pnl"),
                        "unrealized_pnl_pct": position.get("unrealized_pnl_pct"),
                        "funding_paid": position.get("funding_paid")
                    }
                    
                return {"success": False, "error": "Position not found"}
                
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_all_positions(self) -> List[Dict]:
        """Get all open positions"""
        try:
            session = await self._get_session()
            url = f"{self.KANA_API}/positions"
            
            async with session.get(url) as response:
                if response.status == 200:
                    positions = await response.json()
                    return positions
                return []
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

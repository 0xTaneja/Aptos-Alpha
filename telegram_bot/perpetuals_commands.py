"""
Perpetuals Trading Commands for Telegram Bot
Integrates Merkle Trade and Kana Labs perpetuals
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import Dict, List

logger = logging.getLogger(__name__)

class PerpetualsCommands:
    """Handles perpetuals trading commands"""
    
    def __init__(self, merkle_perps, kana_futures, database):
        """
        Initialize perpetuals commands
        
        Args:
            merkle_perps: MerklePerpetuals instance
            kana_futures: KanaFutures instance
            database: DatabaseManager instance
        """
        self.merkle = merkle_perps
        self.kana = kana_futures
        self.db = database
        
        logger.info("Initialized Perpetuals Commands")
    
    async def perp_markets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available perpetual markets"""
        try:
            message = "📊 **PERPETUAL MARKETS**\n\n"
            message += "**Merkle Trade:**\n"
            
            for symbol in self.merkle.SUPPORTED_SYMBOLS:
                market = await self.merkle.get_market_info(symbol)
                if market.get("success"):
                    message += f"• {symbol}\n"
                    message += f"  Price: ${market['mark_price']:.2f}\n"
                    message += f"  Funding: {market['funding_rate']:.4f}%\n"
                    message += f"  Max Leverage: {market['max_leverage']}x\n\n"
            
            message += "\n**Kana Labs:**\n"
            for symbol in self.kana.SUPPORTED_MARKETS:
                funding = await self.kana.get_funding_rate(symbol)
                if funding.get("success"):
                    message += f"• {symbol}\n"
                    message += f"  Funding: {funding['current_rate']:.4f}%\n\n"
            
            await update.message.reply_text(message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error showing perp markets: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def perp_long(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Open long perpetual position
        Usage: /perp_long <symbol> <size> <leverage>
        Example: /perp_long APT 1.0 10
        """
        try:
            if len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Usage: /perp_long <symbol> <size> <leverage>\n"
                    "Example: /perp_long APT 1.0 10"
                )
                return
            
            symbol = context.args[0].upper()
            if not symbol.endswith("-PERP"):
                symbol += "-PERP"
            
            size = float(context.args[1])
            leverage = int(context.args[2])
            
            # Show confirmation keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Merkle Trade", callback_data=f"perp_long_merkle:{symbol}:{size}:{leverage}"),
                    InlineKeyboardButton("✅ Kana Labs", callback_data=f"perp_long_kana:{symbol}:{size}:{leverage}")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="perp_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Get current prices
            merkle_market = await self.merkle.get_market_info(symbol)
            
            message = f"🚀 **OPEN LONG POSITION**\n\n"
            message += f"Symbol: {symbol}\n"
            message += f"Size: {size}\n"
            message += f"Leverage: {leverage}x\n"
            message += f"Side: LONG\n\n"
            
            if merkle_market.get("success"):
                entry_price = merkle_market["mark_price"]
                collateral = size * entry_price / leverage
                liq_price = await self.merkle.calculate_liquidation_price(entry_price, leverage, True)
                
                message += f"Entry Price: ${entry_price:.2f}\n"
                message += f"Collateral Required: ${collateral:.2f}\n"
                message += f"Liquidation Price: ${liq_price:.2f}\n\n"
            
            message += "Choose venue:"
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error in perp_long: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def perp_short(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Open short perpetual position
        Usage: /perp_short <symbol> <size> <leverage>
        Example: /perp_short APT 1.0 10
        """
        try:
            if len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Usage: /perp_short <symbol> <size> <leverage>\n"
                    "Example: /perp_short APT 1.0 10"
                )
                return
            
            symbol = context.args[0].upper()
            if not symbol.endswith("-PERP"):
                symbol += "-PERP"
            
            size = float(context.args[1])
            leverage = int(context.args[2])
            
            # Show confirmation keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Merkle Trade", callback_data=f"perp_short_merkle:{symbol}:{size}:{leverage}"),
                    InlineKeyboardButton("✅ Kana Labs", callback_data=f"perp_short_kana:{symbol}:{size}:{leverage}")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="perp_cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Get current prices
            merkle_market = await self.merkle.get_market_info(symbol)
            
            message = f"📉 **OPEN SHORT POSITION**\n\n"
            message += f"Symbol: {symbol}\n"
            message += f"Size: {size}\n"
            message += f"Leverage: {leverage}x\n"
            message += f"Side: SHORT\n\n"
            
            if merkle_market.get("success"):
                entry_price = merkle_market["mark_price"]
                collateral = size * entry_price / leverage
                liq_price = await self.merkle.calculate_liquidation_price(entry_price, leverage, False)
                
                message += f"Entry Price: ${entry_price:.2f}\n"
                message += f"Collateral Required: ${collateral:.2f}\n"
                message += f"Liquidation Price: ${liq_price:.2f}\n\n"
            
            message += "Choose venue:"
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error in perp_short: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def perp_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all open perpetual positions"""
        try:
            message = "📊 **OPEN PERPETUAL POSITIONS**\n\n"
            
            # Merkle positions
            merkle_positions = await self.merkle.get_all_positions()
            if merkle_positions:
                message += "**Merkle Trade:**\n"
                for pos in merkle_positions:
                    pnl_emoji = "🟢" if pos.get("unrealized_pnl", 0) >= 0 else "🔴"
                    message += f"{pnl_emoji} {pos['symbol']} {pos['side']} {pos['leverage']}x\n"
                    message += f"  Size: {pos['size']}\n"
                    message += f"  Entry: ${pos['entry_price']:.2f}\n"
                    message += f"  Current: ${pos.get('current_price', 0):.2f}\n"
                    message += f"  PnL: ${pos.get('unrealized_pnl', 0):.2f} ({pos.get('unrealized_pnl_percentage', 0):.2f}%)\n"
                    message += f"  Liq: ${pos['liquidation_price']:.2f}\n"
                    message += f"  ID: `{pos['position_id']}`\n\n"
            
            # Kana positions
            kana_positions = await self.kana.get_all_positions()
            if kana_positions:
                message += "**Kana Labs:**\n"
                for pos in kana_positions:
                    pnl_emoji = "🟢" if pos.get("unrealized_pnl", 0) >= 0 else "🔴"
                    message += f"{pnl_emoji} {pos['symbol']} {pos['side']} {pos['leverage']}x\n"
                    message += f"  Size: {pos['size']}\n"
                    message += f"  Entry: ${pos['entry_price']:.2f}\n"
                    message += f"  PnL: ${pos.get('unrealized_pnl', 0):.2f}\n"
                    message += f"  ID: `{pos['position_id']}`\n\n"
            
            if not merkle_positions and not kana_positions:
                message += "No open positions"
            
            await update.message.reply_text(message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error showing positions: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def perp_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Close a perpetual position
        Usage: /perp_close <position_id>
        """
        try:
            if len(context.args) < 1:
                await update.message.reply_text("❌ Usage: /perp_close <position_id>")
                return
            
            position_id = context.args[0]
            
            # Try Merkle first
            result = await self.merkle.close_position(position_id)
            
            if not result.get("success"):
                # Try Kana
                result = await self.kana.close_position(position_id)
            
            if result.get("success"):
                pnl_emoji = "🟢" if result.get("realized_pnl", 0) >= 0 else "🔴"
                message = f"{pnl_emoji} **POSITION CLOSED**\n\n"
                message += f"Position ID: `{position_id}`\n"
                message += f"Symbol: {result.get('symbol', 'N/A')}\n"
                message += f"Realized PnL: ${result.get('realized_pnl', 0):.2f}\n"
                message += f"Fees: ${result.get('fees_paid', 0):.2f}\n"
                
                await update.message.reply_text(message, parse_mode="Markdown")
            else:
                await update.message.reply_text(f"❌ Error: {result.get('error', 'Position not found')}")
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def funding_rates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current funding rates across venues"""
        try:
            message = "💰 **FUNDING RATES**\n\n"
            
            for symbol in self.merkle.SUPPORTED_SYMBOLS:
                # Merkle funding
                merkle_funding = await self.merkle.get_funding_rate(symbol)
                
                # Kana funding
                kana_funding = await self.kana.get_funding_rate(symbol)
                
                message += f"**{symbol}**\n"
                
                if merkle_funding.get("success"):
                    rate = merkle_funding["funding_rate"]
                    emoji = "📈" if rate > 0 else "📉"
                    message += f"{emoji} Merkle: {rate:.4f}% ({rate * 365 * 3:.2f}% APY)\n"
                
                if kana_funding.get("success"):
                    rate = kana_funding["current_rate"]
                    emoji = "📈" if rate > 0 else "📉"
                    message += f"{emoji} Kana: {rate:.4f}% ({rate * 365 * 3:.2f}% APY)\n"
                
                message += "\n"
            
            message += "_Funding rates are paid every 8 hours_"
            
            await update.message.reply_text(message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error showing funding rates: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def funding_arb(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Find funding rate arbitrage opportunities"""
        try:
            opportunities = await self.kana.find_funding_arbitrage(threshold=0.005)
            
            if not opportunities:
                await update.message.reply_text("📊 No significant funding arbitrage opportunities found.")
                return
            
            message = "💎 **FUNDING ARBITRAGE OPPORTUNITIES**\n\n"
            
            for opp in opportunities[:5]:  # Top 5
                message += f"**{opp['symbol']}**\n"
                message += f"Funding Rate: {opp['kana_rate']:.4f}%\n"
                message += f"Strategy: {opp['strategy'].upper()}\n"
                message += f"Expected Return: {opp['expected_return']:.2f}% per 8h\n"
                message += f"Annual Yield: {opp['annual_yield']:.2f}%\n\n"
            
            message += "_Fund arbitrage by taking opposite positions on different venues_"
            
            await update.message.reply_text(message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error finding arbitrage: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_perp_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle perpetuals inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        try:
            data = query.data
            
            if data == "perp_cancel":
                await query.edit_message_text("❌ Position cancelled")
                return
            
            # Parse callback data
            parts = data.split(":")
            action = parts[0]  # perp_long_merkle, perp_short_kana, etc.
            
            if len(parts) < 4:
                await query.edit_message_text("❌ Invalid callback data")
                return
            
            symbol = parts[1]
            size = float(parts[2])
            leverage = int(parts[3])
            
            # Determine venue and side
            venue = "merkle" if "merkle" in action else "kana"
            is_long = "long" in action
            
            # Open position
            if venue == "merkle":
                result = await self.merkle.open_position(symbol, size, leverage, is_long)
            else:
                result = await self.kana.open_position(symbol, size, leverage, is_long)
            
            if result.get("success"):
                side_emoji = "🚀" if is_long else "📉"
                message = f"{side_emoji} **POSITION OPENED**\n\n"
                message += f"Venue: {venue.upper()}\n"
                message += f"Symbol: {symbol}\n"
                message += f"Side: {'LONG' if is_long else 'SHORT'}\n"
                message += f"Size: {size}\n"
                message += f"Leverage: {leverage}x\n"
                message += f"Entry: ${result.get('entry_price', 0):.2f}\n"
                message += f"Liquidation: ${result.get('liquidation_price', 0):.2f}\n"
                message += f"Position ID: `{result.get('position_id')}`\n"
                
                await query.edit_message_text(message, parse_mode="Markdown")
            else:
                await query.edit_message_text(f"❌ Error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error handling perp callback: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

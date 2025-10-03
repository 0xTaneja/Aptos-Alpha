"""
Aptos Trading Commands for Telegram Bot
Handles all trading-related commands for the Aptos trading bot
"""
import logging
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account as AptosAccount

logger = logging.getLogger(__name__)

class AptosTradeCommands:
    """Handles Aptos trading commands for the Telegram bot"""
    
    def __init__(self, wallet_manager=None, trading_engine=None):
        self.wallet_manager = wallet_manager
        self.trading_engine = trading_engine
        
    async def handle_buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command for Aptos tokens"""
        user_id = update.effective_user.id
        
        # Check if user has wallet
        if not self.wallet_manager:
            await update.message.reply_text("❌ Trading system not available.")
            return
            
        wallet = await self.wallet_manager.get_user_wallet(user_id)
        if not wallet:
            await update.message.reply_text(
                "❌ No Aptos wallet found. Use `/start` to create one.",
                parse_mode='Markdown'
            )
            return
            
        # Parse command arguments
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "📝 **Usage:** `/buy <token> <amount>`\n\n"
                "**Example:** `/buy APT 10`\n"
                "**Example:** `/buy USDC 100`",
                parse_mode='Markdown'
            )
            return
            
        token = args[0].upper()
        try:
            amount = float(args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return
            
        # Execute buy order
        await self._execute_buy_order(update, user_id, token, amount)
    
    async def handle_sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command for Aptos tokens"""
        user_id = update.effective_user.id
        
        # Check if user has wallet
        if not self.wallet_manager:
            await update.message.reply_text("❌ Trading system not available.")
            return
            
        wallet = await self.wallet_manager.get_user_wallet(user_id)
        if not wallet:
            await update.message.reply_text(
                "❌ No Aptos wallet found. Use `/start` to create one.",
                parse_mode='Markdown'
            )
            return
            
        # Parse command arguments
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "📝 **Usage:** `/sell <token> <amount>`\n\n"
                "**Example:** `/sell APT 5`\n"
                "**Example:** `/sell USDC 50`",
                parse_mode='Markdown'
            )
            return
            
        token = args[0].upper()
        try:
            amount = float(args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return
            
        # Execute sell order
        await self._execute_sell_order(update, user_id, token, amount)
    
    async def handle_balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command to show Aptos wallet balance"""
        user_id = update.effective_user.id
        
        if not self.wallet_manager:
            await update.message.reply_text("❌ Wallet system not available.")
            return
            
        wallet = await self.wallet_manager.get_user_wallet(user_id)
        if not wallet:
            await update.message.reply_text(
                "❌ No Aptos wallet found. Use `/start` to create one.",
                parse_mode='Markdown'
            )
            return
            
        # Get wallet status
        status = await self.wallet_manager.get_wallet_status(user_id)
        balance = status.get('balance', 0)
        
        balance_msg = (
            f"💰 **Your Aptos Wallet Balance**\n\n"
            f"**APT Balance:** {balance:.4f} APT\n"
            f"**USD Value:** ~${balance * 8.5:.2f}\n\n"  # Approximate APT price
            f"**Wallet Address:** `{wallet['address'][:10]}...{wallet['address'][-6:]}`"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_balance_{user_id}")],
            [InlineKeyboardButton("📊 View Portfolio", callback_data=f"view_portfolio_{user_id}")]
        ]
        
        await update.message.reply_text(
            balance_msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command to show trading positions"""
        user_id = update.effective_user.id
        
        if not self.wallet_manager:
            await update.message.reply_text("❌ Trading system not available.")
            return
            
        # Get portfolio data
        portfolio = await self.wallet_manager.get_user_portfolio(user_id)
        
        if portfolio['status'] != 'success':
            await update.message.reply_text(
                f"❌ Error getting portfolio: {portfolio.get('message', 'Unknown error')}",
                parse_mode='Markdown'
            )
            return
            
        # Format portfolio message
        portfolio_msg = (
            f"📊 **Your Aptos Portfolio**\n\n"
            f"**Total Value:** {portfolio['account_value']:.2f} APT\n"
            f"**Available:** {portfolio['available_balance']:.2f} APT\n"
            f"**P&L:** {portfolio['unrealized_pnl']:+.2f} APT\n\n"
        )
        
        # Add positions
        if portfolio['positions']:
            portfolio_msg += "**Positions:**\n"
            for pos in portfolio['positions']:
                portfolio_msg += (
                    f"• {pos['coin']}: {pos['size']:+.4f} "
                    f"(Entry: {pos['entry_price']:.4f}, "
                    f"P&L: {pos['unrealized_pnl']:+.2f})\n"
                )
        else:
            portfolio_msg += "**Positions:** None\n"
            
        # Add recent trades
        if portfolio['recent_trades']:
            portfolio_msg += "\n**Recent Trades:**\n"
            for trade in portfolio['recent_trades'][:3]:  # Show last 3 trades
                portfolio_msg += (
                    f"• {trade['side'].upper()} {trade['size']:.4f} {trade['coin']} "
                    f"@ {trade['price']:.4f} APT\n"
                )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_portfolio_{user_id}")],
            [InlineKeyboardButton("📈 Trading History", callback_data=f"trading_history_{user_id}")]
        ]
        
        await update.message.reply_text(
            portfolio_msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_orders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /orders command to show active orders"""
        user_id = update.effective_user.id
        
        if not self.trading_engine:
            await update.message.reply_text("❌ Trading engine not available.")
            return
            
        # Get active orders
        try:
            orders = await self.trading_engine.get_user_orders(user_id)
            
            if not orders:
                await update.message.reply_text(
                    "📋 **Active Orders**\n\n"
                    "No active orders found.\n\n"
                    "Use `/buy` or `/sell` to place orders.",
                    parse_mode='Markdown'
                )
                return
                
            orders_msg = "📋 **Active Orders**\n\n"
            
            for order in orders[:10]:  # Show max 10 orders
                orders_msg += (
                    f"• {order.get('side', 'N/A').upper()} "
                    f"{order.get('size', 0):.4f} {order.get('coin', 'N/A')} "
                    f"@ {order.get('price', 0):.4f} APT\n"
                    f"  Status: {order.get('status', 'Unknown')}\n\n"
                )
                
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_orders_{user_id}")],
                [InlineKeyboardButton("❌ Cancel All", callback_data=f"cancel_all_orders_{user_id}")]
            ]
            
            await update.message.reply_text(
                orders_msg,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            logger.error(f"Error getting orders for user {user_id}: {e}")
            await update.message.reply_text(
                "❌ Error retrieving orders. Please try again later."
            )
    
    async def _execute_buy_order(self, update: Update, user_id: int, token: str, amount: float):
        """Execute a buy order on Aptos"""
        try:
            # Show processing message
            processing_msg = await update.message.reply_text(
                f"🔄 **Processing Buy Order**\n\n"
                f"Buying {amount} {token}...",
                parse_mode='Markdown'
            )
            
            # Execute through trading engine
            if self.trading_engine:
                result = await self.trading_engine.place_market_order(
                    user_id=user_id,
                    token=token,
                    side='buy',
                    amount=amount
                )
                
                if result.get('status') == 'success':
                    success_msg = (
                        f"✅ **Buy Order Executed**\n\n"
                        f"**Token:** {token}\n"
                        f"**Amount:** {amount} {token}\n"
                        f"**Price:** {result.get('price', 'Market')} APT\n"
                        f"**Total Cost:** {result.get('total_cost', 'N/A')} APT\n\n"
                        f"**Transaction ID:** `{result.get('tx_hash', 'N/A')}`"
                    )
                    
                    await processing_msg.edit_text(success_msg, parse_mode='Markdown')
                else:
                    error_msg = (
                        f"❌ **Buy Order Failed**\n\n"
                        f"Error: {result.get('message', 'Unknown error')}\n\n"
                        f"Please check your balance and try again."
                    )
                    
                    await processing_msg.edit_text(error_msg, parse_mode='Markdown')
            else:
                await processing_msg.edit_text(
                    "❌ Trading engine not available. Please try again later.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error executing buy order for user {user_id}: {e}")
            await update.message.reply_text(
                f"❌ Error executing buy order: {str(e)}"
            )
    
    async def _execute_sell_order(self, update: Update, user_id: int, token: str, amount: float):
        """Execute a sell order on Aptos"""
        try:
            # Show processing message
            processing_msg = await update.message.reply_text(
                f"🔄 **Processing Sell Order**\n\n"
                f"Selling {amount} {token}...",
                parse_mode='Markdown'
            )
            
            # Execute through trading engine
            if self.trading_engine:
                result = await self.trading_engine.place_market_order(
                    user_id=user_id,
                    token=token,
                    side='sell',
                    amount=amount
                )
                
                if result.get('status') == 'success':
                    success_msg = (
                        f"✅ **Sell Order Executed**\n\n"
                        f"**Token:** {token}\n"
                        f"**Amount:** {amount} {token}\n"
                        f"**Price:** {result.get('price', 'Market')} APT\n"
                        f"**Total Received:** {result.get('total_received', 'N/A')} APT\n\n"
                        f"**Transaction ID:** `{result.get('tx_hash', 'N/A')}`"
                    )
                    
                    await processing_msg.edit_text(success_msg, parse_mode='Markdown')
                else:
                    error_msg = (
                        f"❌ **Sell Order Failed**\n\n"
                        f"Error: {result.get('message', 'Unknown error')}\n\n"
                        f"Please check your balance and try again."
                    )
                    
                    await processing_msg.edit_text(error_msg, parse_mode='Markdown')
            else:
                await processing_msg.edit_text(
                    "❌ Trading engine not available. Please try again later.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error executing sell order for user {user_id}: {e}")
            await update.message.reply_text(
                f"❌ Error executing sell order: {str(e)}"
            )

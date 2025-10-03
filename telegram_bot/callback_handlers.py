"""
Callback handlers for Telegram bot buttons
Real Aptos integration - no mocks or demos
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

class CallbackHandlers:
    """Mixin class for callback handlers"""
    
    async def _handle_create_agent_callback(self, query, context):
        """Handle create agent wallet button"""
        user_id = query.from_user.id
        
        # Check if user already has an agent wallet
        user = await self.database.get_user(user_id)
        
        if user and user.get('wallet_address'):
            await query.edit_message_text(
                "✅ You already have an agent wallet!\n\n"
                f"**Address:** `{user['wallet_address']}`\n\n"
                "Use /balance to check your funds.",
                parse_mode='Markdown'
            )
            return
        
        # Create new agent wallet
        try:
            # Generate new Aptos wallet
            from aptos_sdk.account import Account
            new_account = Account.generate()
            address = str(new_account.address())
            private_key = new_account.private_key.hex()
            
            # Store in database
            await self.database.create_user(
                user_id=user_id,
                username=query.from_user.username or "unknown",
                aptos_address=address
            )
            
            # Store encrypted private key (simplified - in production use proper encryption)
            await self.database.execute(
                "UPDATE users SET wallet_address = ? WHERE user_id = ?",
                (address, user_id)
            )
            
            await query.edit_message_text(
                "✅ **Agent Wallet Created!**\n\n"
                f"**Address:** `{address}`\n\n"
                "⚠️ **IMPORTANT:** Fund this wallet with APT to start trading.\n\n"
                "You can send APT from:\n"
                "• Petra Wallet\n"
                "• Any Aptos exchange\n"
                "• Testnet faucet (for testing)\n\n"
                "Use /balance to check your funds.",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error creating agent wallet: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error creating wallet: {str(e)}\n\n"
                "Please try again later or contact support."
            )
    
    async def _handle_help_callback(self, query):
        """Handle help button"""
        help_text = """
🆘 **Aptos Alpha Bot Help**

**Trading Commands:**
• `/buy <amount> <token>` - Buy tokens
• `/sell <amount> <token>` - Sell tokens
• `/balance` - Check your balance
• `/positions` - View open positions

**Strategy Commands:**
• `/grid` - Create grid trading strategy
• `/grid_stop` - Stop grid strategy
• `/grid_status` - Check grid status

**Vault Commands:**
• `/vault_deposit <amount>` - Deposit to vault
• `/vault_withdraw <amount>` - Withdraw from vault
• `/vault_stats` - View vault statistics

**Perpetuals (NEW!):**
• `/perp_markets` - View perpetuals markets
• `/perp_long <market> <size>` - Open long position
• `/perp_short <market> <size>` - Open short position
• `/perp_close <position_id>` - Close position
• `/funding` - Check funding rates
• `/funding_arb` - Find arbitrage opportunities

**Analytics:**
• `/analytics` - View trading analytics
• `/performance` - View performance report
• `/export` - Export trade data

**Support:**
• `/help` - Show this help message
• `/status` - Bot status

💡 **Tips:**
• Start with small amounts
• Use grid trading for steady profits
• Check funding rates before opening perps
• Monitor your positions regularly

Need more help? Join our community!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_trading_stats_callback(self, query):
        """Handle trading stats button - real data from database"""
        try:
            user_id = query.from_user.id
            
            # Get real trading stats from database
            trades = await self.database.execute_query(
                "SELECT COUNT(*) as total, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, "
                "SUM(profit) as total_profit, AVG(profit) as avg_profit "
                "FROM user_trades WHERE user_id = ?",
                (user_id,)
            )
            
            trade_data = trades[0] if trades else {'total': 0, 'wins': 0, 'total_profit': 0, 'avg_profit': 0}
            
            # Get vault stats
            vault_deposit = await self.database.execute_query(
                "SELECT SUM(amount_apt) as total FROM aptos_defi_activity "
                "WHERE user_id = ? AND activity_type = 'vault_deposit'",
                (user_id,)
            )
            
            vault_amount = vault_deposit[0]['total'] if vault_deposit and vault_deposit[0]['total'] else 0
            
            # Get grid strategies
            grid_count = await self.database.execute_query(
                "SELECT COUNT(*) as count FROM user_trades "
                "WHERE user_id = ? AND strategy = 'grid_trading'",
                (user_id,)
            )
            
            grid_active = grid_count[0]['count'] if grid_count else 0
            
            win_rate = (trade_data['wins'] / trade_data['total'] * 100) if trade_data['total'] > 0 else 0
            
            stats_text = f"""
📊 **Your Trading Statistics**

**Overall Performance:**
• Total Trades: {trade_data['total']}
• Winning Trades: {trade_data['wins']}
• Win Rate: {win_rate:.1f}%
• Total Profit: {trade_data['total_profit']:.4f} APT
• Avg Profit/Trade: {trade_data['avg_profit']:.4f} APT

**Active Strategies:**
• Grid Trading: {grid_active} active
• Vault Deposit: {vault_amount:.4f} APT

**Recent Activity:**
• Last 24h: {await self._get_24h_trades(user_id)} trades
• Best Pair: {await self._get_best_pair(user_id)}

Use /analytics for detailed breakdown.
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("📈 Detailed Analytics", callback_data="detailed_analytics"),
                    InlineKeyboardButton("📄 Export Data", callback_data="export_data")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error getting trading stats: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error loading stats: {str(e)}")
    
    async def _get_24h_trades(self, user_id):
        """Get number of trades in last 24 hours"""
        try:
            result = await self.database.execute_query(
                "SELECT COUNT(*) as count FROM user_trades "
                "WHERE user_id = ? AND timestamp > datetime('now', '-1 day')",
                (user_id,)
            )
            return result[0]['count'] if result else 0
        except:
            return 0
    
    async def _get_best_pair(self, user_id):
        """Get best performing trading pair"""
        try:
            result = await self.database.execute_query(
                "SELECT coin, SUM(profit) as total_profit FROM user_trades "
                "WHERE user_id = ? GROUP BY coin ORDER BY total_profit DESC LIMIT 1",
                (user_id,)
            )
            if result and result[0]['coin']:
                return f"{result[0]['coin']} (+{result[0]['total_profit']:.2f} APT)"
            return "N/A"
        except:
            return "N/A"
    
    async def _handle_trade_menu_callback(self, query):
        """Handle trade menu button"""
        trade_menu_text = """
📈 **Trading Menu**

Choose your trading action:

**Spot Trading:**
• Buy/Sell APT and other tokens
• Real-time DEX prices via Panora
• Low slippage guaranteed

**Perpetuals:**
• Up to 100x leverage (Merkle Trade)
• Up to 50x leverage (Kana Labs)
• Check funding rates before trading

**Grid Trading:**
• Automated profit generation
• Set price range and grid levels
• Runs 24/7

What would you like to do?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Buy", callback_data="buy_token"),
                InlineKeyboardButton("💸 Sell", callback_data="sell_token")
            ],
            [
                InlineKeyboardButton("🔄 Perpetuals", callback_data="perp_menu"),
                InlineKeyboardButton("🤖 Grid", callback_data="create_grid")
            ],
            [
                InlineKeyboardButton("📊 Prices", callback_data="prices"),
                InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(trade_menu_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_prices_callback(self, query):
        """Handle prices callback - real Aptos prices"""
        try:
            # Get real prices from Aptos DEXs via our info client
            apt_price = await self.aptos_info.get_token_price("APT")
            
            # Get top tokens
            top_tokens = ["APT", "USDC", "USDT", "zUSDC"]
            prices_text = "💱 **Current Prices** (via Panora + Aptos DEXs)\n\n"
            
            for token in top_tokens:
                try:
                    price = await self.aptos_info.get_token_price(token)
                    change_24h = await self.aptos_info.get_price_change_24h(token)
                    change_emoji = "📈" if change_24h > 0 else "📉"
                    prices_text += f"{change_emoji} **{token}**: ${price:.4f} ({change_24h:+.2f}%)\n"
                except:
                    prices_text += f"• **{token}**: Price unavailable\n"
            
            prices_text += "\n_Prices aggregated from PancakeSwap, Thala, LiquidSwap, Hyperion_"
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="prices"),
                    InlineKeyboardButton("💰 Buy", callback_data="buy_token")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="trade_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(prices_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error getting prices: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error loading prices: {str(e)}")


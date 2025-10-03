import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
import time
from typing import Any, Dict, List, Optional
import json

# Add parent directory to path for imports
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# This might be better if main_bot.py is in trading_engine, and telegram_bot is a sibling
project_root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Moves to hyperliqbot/
if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)


from strategies.aptos_network import AptosConnector, AptosMonitor
from strategies.seedify_imc import AptosIMCManager
from trading_engine.base_trader import AptosOptimizedTrader

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account as AptosAccount

from trading_engine.config import TradingConfig

# Import the new TelegramAuthHandler
from telegram_bot.telegram_auth_handler import TelegramAuthHandler


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramTradingBot:
    """
    Advanced Telegram trading bot with Aptos blockchain integration
    """
    
    def __init__(self, token: str, config: Dict, vault_manager=None, trading_engine=None, database=None, user_manager=None):
        self.token = token
        self.main_config = config # Store the main application config
        self.logger = logging.getLogger(__name__)
        
        # Dependency injection from main.py - Core Components
        self.vault_manager = vault_manager
        self.trading_engine = trading_engine
        self.database = database
        self.user_manager = user_manager
        
        self.user_sessions: Dict[int, Dict[str, Any]] = {} # Centralized user sessions
        self.active_strategies = {}
        self.profit_tracking = {}
        
        # Components injected by main.py after initialization (if any)
        self.profit_bot = None # Example, if used
        self.strategies = {} # Example, if used
        self.websocket_manager = None # Example, if used
        
        self.referral_code = self.main_config.get("referral_code", "HYPERBOT")
        
        # Initialize trading configuration (bot's internal trading params)
        self.trading_config = TradingConfig()

        # Initialize TelegramAuthHandler
        # Get bot_username and node_url from the main config if available
        bot_username = self.main_config.get("telegram", {}).get("bot_username", "AptosAlphaBotUsername")
        aptos_node_url = self.main_config.get("aptos", {}).get("node_url", "https://fullnode.mainnet.aptoslabs.com/v1")
        self.auth_handler = TelegramAuthHandler(
            user_sessions=self.user_sessions, 
            node_url=aptos_node_url,
            bot_username=bot_username
        )
        
        # Initialize Telegram Application
        self.app = Application.builder().token(self.token).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Setup all command and callback handlers"""
        # Main commands
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        # Delegate /connect to TelegramAuthHandler
        self.app.add_handler(CommandHandler("connect", self.auth_handler.handle_connect_command))
        
        self.app.add_handler(CommandHandler("status", self.status_command)) # New status command
        self.app.add_handler(CommandHandler("portfolio", self.show_portfolio))
        self.app.add_handler(CommandHandler("trade", self.trade_menu))
        self.app.add_handler(CommandHandler("strategies", self.strategies_menu))
        self.app.add_handler(CommandHandler("profits", self.show_profits))
        self.app.add_handler(CommandHandler("aptos", self.aptos_defi_menu))
        self.app.add_handler(CommandHandler("seedify", self.seedify_menu))
        
        # Add missing command handlers
        self.app.add_handler(CommandHandler("deposit", self.handle_deposit_vault))
        self.app.add_handler(CommandHandler("stats", self.handle_vault_stats)) # Renamed from vault_info_command
        self.app.add_handler(CommandHandler("withdraw", self.handle_withdrawal_request))
        
        # New integrated handlers
        self.app.add_handler(CommandHandler("ai", self.execute_ai_strategy))
        self.app.add_handler(CommandHandler("gas", self.check_gas_prices))
        self.app.add_handler(CommandHandler("bridge", self.bridge_status))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_messages))

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Shows the current connection status for the user."""
        user_id = update.effective_user.id
        status_text = self.auth_handler.get_session_info_text(user_id)
        await update.message.reply_text(status_text, parse_mode='Markdown')

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with vault focus"""
        user_id = update.effective_user.id
        
        # Check for referral
        referrer_id = None
        if context.args and context.args[0].startswith("ref_"):
            referrer_id = int(context.args[0].replace("ref_", ""))
        
        welcome_message = f"""🚀 Aptos Alpha Trading Bot

💰 Revolutionary Trading System:
• Secure Aptos wallet integration
• Earn from 4 alpha strategies simultaneously
• Get 90% of profits, we take 10%
• Start with just 10 APT minimum

🎯 Alpha Strategies Running 24/7:
• DEX Arbitrage (PancakeSwap, Thala, LiquidSwap)
• APT Staking (7% APR + rewards)
• Grid Trading (capture volatility)
• Yield Farming (maximize APY)

📈 Current Performance:
• Daily Volume: 50K+ APT 
• Vault TVL: 5K+ APT
• Average Daily Return: 0.2%
• Staking Rewards: 100+ APT daily

🎁 Referral Bonus:
• Refer friends = 1% bonus on their deposits
• Your link: t.me/AptosAlphaBot?start=ref_{user_id}

💡 Quick Start:
1. /deposit - Add APT to vault
2. /stats - Track your profits  
3. /withdraw - Request withdrawal

Ready to join the Aptos alpha?"""
        
        keyboard = [
            [KeyboardButton("💰 Deposit to Vault"), KeyboardButton("📊 Vault Stats")],
            [KeyboardButton("🏆 Competition Status"), KeyboardButton("🎁 Referral Link")],
            [KeyboardButton("💸 Request Withdrawal"), KeyboardButton("📈 Live Trading")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup
        )
        
        # Store referrer for later
        if referrer_id:
            context.user_data["referrer_id"] = referrer_id
    
    async def connect_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        DEPRECATED: This method is now handled by TelegramAuthHandler.
        The CommandHandler for /connect directly calls auth_handler.handle_connect_command.
        This method can be removed or kept as a placeholder if other logic relied on it.
        """
        await self.auth_handler.handle_connect_command(update, context)

    async def show_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user portfolio using REAL Aptos data and injected components"""
        user_id = update.effective_user.id
        
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.message.reply_text(error_message)
            return
        
        try:
            session = self.user_sessions[user_id] # Session is managed by AuthHandler
            client = session["client"]
            # Address in session is always the main address, even if agent is used
            main_address = session["address"] 
            
            # Get account resources and balance
            resources = await client.account_resources(main_address)
            apt_balance = await client.account_balance(main_address)
            
            # Parse token balances and positions
            token_balances = {}
            total_value = apt_balance / 100_000_000  # Convert from octas to APT
            
            for resource in resources:
                if "CoinStore" in resource["type"]:
                    type_parts = resource["type"].split("<")
                    if len(type_parts) > 1:
                        token_type = type_parts[1].split(">")[0]
                        coin_data = resource["data"]["coin"]
                        balance = int(coin_data["value"])
                        
                        if balance > 0:
                            token_symbol = token_type.split("::")[-1]
                            balance_formatted = balance / 100_000_000
                            token_balances[token_symbol] = {
                                "balance": balance,
                                "balance_formatted": balance_formatted,
                                "token_type": token_type
                            }
                            
                            # Add to total value (simplified - would need price conversion)
                            if token_symbol != "AptosCoin":
                                total_value += balance_formatted
            
            # Get additional data from injected database
            user_stats = {}
            if self.database:
                try:
                    user_stats = await self.database.get_user_stats(user_id)
                except Exception as e:
                    logger.warning(f"Database error: {e}")
            
            portfolio_text = f"📊 **Your Aptos Portfolio**\n\n"
            portfolio_text += f"💰 APT Balance: {apt_balance / 100_000_000:,.8f} APT\n"
            portfolio_text += f"📈 Total Value: ~{total_value:,.2f} APT\n"
            
            if user_stats.get('vault_balance'):
                portfolio_text += f"🏦 Vault Balance: {user_stats['vault_balance']:,.2f} APT\n"
            
            portfolio_text += "\n"
            
            if token_balances:
                portfolio_text += "**Token Holdings:**\n"
                for symbol, data in list(token_balances.items())[:5]:  # Show top 5 tokens
                    balance_formatted = data["balance_formatted"]
                    if balance_formatted > 0.001:  # Only show significant balances
                        portfolio_text += f"{symbol}: {balance_formatted:,.6f}\n"
                portfolio_text += "\n"
            else:
                portfolio_text += "No token holdings\n\n"
            
            # Add action buttons
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_portfolio")],
                [InlineKeyboardButton("📈 Start Trading", callback_data="open_trading")],
                [InlineKeyboardButton("🤖 Auto Strategies", callback_data="auto_strategies")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                portfolio_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Portfolio error: {e}")
            await update.message.reply_text(f"❌ Error fetching portfolio: {str(e)}")

    async def trade_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trading menu using injected trading_engine"""
        user_id = update.effective_user.id
        
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            # Check if query or message to reply appropriately
            if update.callback_query:
                await update.callback_query.edit_message_text(error_message)
            else:
                await update.message.reply_text(error_message)
            return
        
        if not self.trading_engine:
            await update.message.reply_text("❌ Trading engine not available")
            return
        
        keyboard = [
            [InlineKeyboardButton("📈 Buy Order", callback_data="buy_order")],
            [InlineKeyboardButton("📉 Sell Order", callback_data="sell_order")],
            [InlineKeyboardButton("🎯 Market Making", callback_data="market_making")],
            [InlineKeyboardButton("⚡ Quick Trade", callback_data="quick_trade")],
            [InlineKeyboardButton("📊 Order Book", callback_data="orderbook")],
            [InlineKeyboardButton("💰 P&L Tracker", callback_data="pnl_tracker")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get trading engine status using injected component
        try:
            engine_status = await self.trading_engine.get_status()
            status_text = f"🔄 Engine Status: {'✅ Active' if engine_status.get('active') else '❌ Inactive'}\n"
        except Exception as e:
            logger.warning(f"Trading engine status error: {e}")
            status_text = "🔄 Engine Status: Unknown\n"
        
        await update.message.reply_text(
            f"📈 **Trading Menu**\n\n"
            f"{status_text}\n"
            f"Choose your trading action:",
            reply_markup=reply_markup
        )
    
    async def strategies_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show automated strategies menu using injected strategies"""
        user_id = update.effective_user.id
        
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            if update.callback_query:
                await update.callback_query.edit_message_text(error_message)
            else:
                await update.message.reply_text(error_message)
            return
        
        keyboard = [
            [InlineKeyboardButton("🤖 DCA Strategy", callback_data="dca_strategy")],
            [InlineKeyboardButton("📊 Grid Trading", callback_data="grid_strategy")],
            [InlineKeyboardButton("⚡ Scalping Bot", callback_data="scalping_bot")],
            [InlineKeyboardButton("🎯 Arbitrage", callback_data="arbitrage")],
            [InlineKeyboardButton("📈 Trend Following", callback_data="trend_following")],
            [InlineKeyboardButton("⚙️ Strategy Settings", callback_data="strategy_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Show active strategies using injected strategies
        active_count = len(self.active_strategies.get(user_id, {}))
        available_strategies = len(self.strategies) if self.strategies else 0
        
        await update.message.reply_text(
            f"🤖 **Automated Strategies**\n\n"
            f"Available Strategies: {available_strategies}\n"
            f"Your Active Strategies: {active_count}\n\n"
            f"Choose a strategy to configure:",
            reply_markup=reply_markup
        )
    
    async def aptos_defi_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Aptos DeFi ecosystem menu"""
        user_id = update.effective_user.id
        
        keyboard = [
            [InlineKeyboardButton("🥞 PancakeSwap", callback_data="pancakeswap")],
            [InlineKeyboardButton("🌊 Thala Labs", callback_data="thala")],
            [InlineKeyboardButton("💧 LiquidSwap", callback_data="liquidswap")],
            [InlineKeyboardButton("🏦 Aries Markets", callback_data="aries")],
            [InlineKeyboardButton("🐢 Tortuga Staking", callback_data="tortuga")],
            [InlineKeyboardButton("📈 Portfolio Optimizer", callback_data="portfolio_optimizer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🌐 **Aptos DeFi Ecosystem**\n\n"
            "Access leading DeFi protocols:\n\n"
            "🥞 **PancakeSwap** - DEX Trading & Farming\n"
            "🌊 **Thala Labs** - Stablecoins & Yield\n"  
            "💧 **LiquidSwap** - AMM & Liquidity\n"
            "🏦 **Aries Markets** - Lending & Borrowing\n"
            "🐢 **Tortuga** - Liquid Staking\n\n"
            "Choose a protocol:",
            reply_markup=reply_markup
        )
    
    async def seedify_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Seedify IMC menu"""
        user_id = update.effective_user.id
        
        keyboard = [
            [InlineKeyboardButton("🌱 Join IMC Pool", callback_data="join_imc")],
            [InlineKeyboardButton("📊 IMC Performance", callback_data="imc_performance")],
            [InlineKeyboardButton("💰 Volume Farming", callback_data="volume_farming")],
            [InlineKeyboardButton("🎯 Launch Calendar", callback_data="launch_calendar")],
            [InlineKeyboardButton("📈 Revenue Share", callback_data="revenue_share")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🌱 **Seedify IMC System**\n\n"
            "💰 **Benefits:**\n"
            "• Access to $100K+ launches\n"
            "• Pooled investment management\n"
            "• Volume-based maker rebates\n"
            "• Revenue sharing program\n\n"
            "Choose an option:",
            reply_markup=reply_markup
        )
    
    async def show_profits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show profit tracking using REAL data"""
        user_id = update.effective_user.id
        
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.message.reply_text(error_message)
            return
        
        try:
            session = self.user_sessions[user_id]
            # Ensure trader is instantiated in the session by auth_handler or here
            if 'trader' not in session:
                 # Attempt to instantiate trader if not present; ensure ProfitOptimizedTrader is importable
                 # This might be better handled within TelegramAuthHandler when session is created/updated
                try:
                    from trading_engine.base_trader import ProfitOptimizedTrader
                    session['trader'] = ProfitOptimizedTrader(
                        address=session['address'], 
                        info=session['info'], 
                        exchange=session['exchange']
                    )
                except ImportError:
                    logger.error("ProfitOptimizedTrader could not be imported for show_profits.")
                    await update.message.reply_text("❌ Profit tracking module is currently unavailable.")
                    return

            trader = session["trader"]
            
            # Get REAL performance data
            # Assuming trader.track_performance() is an async method
            performance = await trader.track_performance() 
            
            profit_text = f"💰 **Profit Analytics**\n\n"
            profit_text += f"📊 Account Value: ${performance.get('account_value', 0):,.2f}\n"
            profit_text += f"📈 Total P&L: ${performance.get('total_pnl', 0):+,.2f}\n"
            profit_text += f"💸 Fees Paid: ${performance.get('total_fees_paid', 0):,.4f}\n"
            profit_text += f"💰 Rebates Earned: ${performance.get('total_rebates_earned', 0):,.4f}\n"
            profit_text += f"🎯 Net Profit: ${performance.get('net_profit', 0):+,.2f}\n\n"
            
            profit_text += f"📊 **Statistics:**\n"
            profit_text += f"• Total Trades: {performance.get('trade_count', 0)}\n"
            profit_text += f"• Avg Profit/Trade: ${performance.get('avg_profit_per_trade', 0):+,.2f}\n"
            profit_text += f"• Fee Efficiency: {performance.get('fee_efficiency', 0)*100:.1f}%\n\n"
            
            # Revenue projections
            days_connected = max(1, (datetime.now() - session['connected_at']).days)
            daily_profit = performance.get('net_profit', 0) / days_connected
            monthly_projection = daily_profit * 30
            
            profit_text += f"📈 **Projections:**\n"
            profit_text += f"• Daily Avg: ${daily_profit:+,.2f}\n"
            profit_text += f"• Monthly Est: ${monthly_projection:+,.2f}\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_profits")],
                [InlineKeyboardButton("📊 Detailed Report", callback_data="detailed_report")],
                [InlineKeyboardButton("💰 Place Maker Order", callback_data="place_maker_order")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                profit_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Profits error: {e}")
            await update.message.reply_text(f"❌ Error fetching profits: {str(e)}")
    
    async def execute_ai_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute AI-powered trading strategy"""
        user_id = update.effective_user.id
        
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.message.reply_text(error_message)
            return
        
        try:
            ai_engine = self.ai_engines.get(user_id)
            if not ai_engine:
                await update.message.reply_text("❌ AI engine not initialized")
                return
            
            # Train models and generate signals
            coins = ["BTC", "ETH", "SOL"]
            signals = []
            
            for coin in coins:
                # Train model
                train_result = await ai_engine.train_ml_model(coin)
                if train_result["status"] == "model_trained":
                    # Generate signal
                    signal = await ai_engine.generate_ai_signal(coin)
                    if signal and hasattr(signal, 'signal') and signal.signal != "HOLD":
                        signals.append(signal)
            
            if signals:
                response = "🤖 **AI Trading Signals**\n\n"
                for signal in signals:
                    response += f"📊 {signal.coin}: {signal.signal}\n"
                    response += f"🎯 Target: ${signal.price_target:.2f}\n"
                    response += f"🛡️ Stop: ${signal.stop_loss:.2f}\n"
                    response += f"📈 Confidence: {signal.confidence:.1%}\n\n"
                
                keyboard = [
                    [InlineKeyboardButton("Execute All Signals", callback_data="execute_ai_signals")],
                    [InlineKeyboardButton("Execute Manually", callback_data="manual_ai_execution")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text("🤖 No AI signals generated at this time. Markets may be in consolidation.")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error running AI strategy: {str(e)}")
    
    async def check_gas_prices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check Aptos transaction fees"""
        try:
            aptos_connector = AptosConnector(self.main_config)
            monitor = AptosMonitor(aptos_connector)
            
            fee_data = await monitor.check_transaction_fees()
            
            if fee_data.get("error"):
                await update.message.reply_text(f"❌ Error: {fee_data['error']}")
                return
            
            current_fee = fee_data.get("current_fee_octas", 100)
            recommendation = fee_data.get("recommendation", "normal")
            
            fee_message = f"⛽ **Aptos Transaction Fees**\n\n"
            fee_message += f"💰 Current Fee: {current_fee} octas\n"
            fee_message += f"💰 Current Fee: {current_fee / 100_000_000:.8f} APT\n"
            fee_message += f"📊 Status: {recommendation.replace('_', ' ').title()}\n\n"
            
            if recommendation == "low_cost":
                fee_message += "✅ Great time for transactions!"
            elif recommendation == "high_cost":
                fee_message += "⚠️ Network congestion detected"
            else:
                fee_message += "🔄 Normal transaction fees"
            
            await update.message.reply_text(fee_message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error checking transaction fees: {str(e)}")
    
    async def bridge_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check Aptos bridge status"""
        try:
            aptos_connector = AptosConnector(self.main_config)
            network_status = await aptos_connector.get_network_status()
            
            bridge_message = f"🌉 **Aptos Bridge Status**\n\n"
            bridge_message += f"📡 Network: {network_status.get('network', 'Mainnet')}\n"
            bridge_message += f"🔗 Connected: {'✅' if network_status.get('connected') else '❌'}\n"
            
            if network_status.get('connected'):
                bridge_message += f"📊 Latest Version: {network_status.get('ledger_version', 'N/A')}\n"
                bridge_message += f"⛽ Base Fee: {network_status.get('gas_unit_price', 100)} octas/gas\n"
                bridge_message += f"🌉 **Available Bridges:**\n"
                bridge_message += f"• Wormhole (ETH ↔ APT)\n"
                bridge_message += f"• LayerZero (Multi-chain)\n"
                bridge_message += f"• Aptos Bridge (Official)\n"
            
            await update.message.reply_text(bridge_message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error checking bridge status: {str(e)}")
    
    async def handle_volume_farming(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Handle volume farming strategy"""
        # Validate session using user_id from argument
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        try:
            session = self.user_sessions[user_id] # Use validated session
            
            # Instantiate AptosIMCManager with user's session components
            # and the bot's main config
            seedify_manager = AptosIMCManager(
                aptos_client=session['client'],
                aptos_account=session['account'],
                config=self.main_config, # Bot's main config
                address=session['address'] # User's address from session
            )
            
            # Get user account value
            apt_balance = await session["client"].account_balance(session["address"])
            account_value = apt_balance / 100_000_000  # Convert from octas to APT
            
            strategy_result = await seedify_manager.create_volume_farming_strategy(account_value)
            
            if strategy_result.get("status") == "success":
                strategy = strategy_result["strategy"]
                
                keyboard = [
                    [InlineKeyboardButton("🚀 Start Volume Farming", callback_data="start_volume_farming")],
                    [InlineKeyboardButton("📊 Calculate Rebates", callback_data="calculate_rebates")],
                    [InlineKeyboardButton("⚙️ Farming Settings", callback_data="farming_settings")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.callback_query.edit_message_text(
                    f"💰 **Volume Farming Strategy**\n\n"
                    f"💼 Capital Allocated: {strategy['capital_allocated']:,.2f} APT\n"
                    f"📊 Daily Volume Target: {strategy['daily_volume_target']:,.2f} APT\n"
                    f"💸 Expected Daily Fees: {strategy['expected_daily_fees']:.4f} APT\n"
                    f"💰 Expected Daily Rewards: {strategy['expected_daily_rebates']:.4f} APT\n"
                    f"🎯 Net Daily Profit: {strategy['net_daily_cost']:.4f} APT\n\n"
                    f"⚠️ **Requirements:**\n"
                    f"• Minimum 10 APT account value\n"
                    f"• DEX liquidity provision\n"
                    f"• 7-day farming cycle\n\n"
                    f"💡 **Strategy:** {strategy['order_strategy']}\n"
                    f"🔄 **Rebalance:** {strategy['rebalance_frequency']}",
                    reply_markup=reply_markup
                )
            else:
                await update.callback_query.edit_message_text(
                    f"❌ **Volume Farming Error**\n\n{strategy_result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id # User who pressed the button
        data = query.data
        
        try:
            # Route to TelegramAuthHandler for agent creation
            if data == "create_agent": # Matches callback_data from TelegramAuthHandler
                await self.auth_handler.create_agent_wallet_for_user(update, context)
                # Clean up temp data if any was stored by old connect_wallet, though new one doesn't use context.user_data for this
                for key_suffix in ["account", "address", "info", "exchange"]:
                    context.user_data.pop(f"temp_{key_suffix}_{user_id}", None)
                return # Callback handled

            # Deprecated callbacks from old connect_wallet, should be removed if handle_connect_command is fully adopted
            elif data.startswith("create_agent_"): # Old format, if still somehow triggered
                logger.warning(f"Deprecated callback 'create_agent_{user_id}' received. Should use 'create_agent'.")
                # Fallback or error, ideally this path is not taken.
                # For safety, can route to new handler if user_id matches.
                requesting_user_id = int(data.split("_")[-1])
                if user_id == requesting_user_id:
                    await self.auth_handler.create_agent_wallet_for_user(update, context)
                else:
                     await query.edit_message_text("❌ Error: This action is not for you.")
                return
            elif data.startswith("direct_key_"): # Old format
                logger.warning(f"Deprecated callback 'direct_key_{user_id}' received. Direct connection is now default from /connect.")
                # The new handle_connect_command already sets up direct session.
                # This callback might be redundant or indicate an old message.
                await query.edit_message_text("ℹ️ Direct connection is established via `/connect`. Use `/status` to check.")
                # Clean up temp data
                for key_suffix in ["account", "address", "info", "exchange"]:
                    context.user_data.pop(f"temp_{key_suffix}_{user_id}", None)
                return

            elif data == "refresh_portfolio":
                # Refresh portfolio by calling show_portfolio
                # show_portfolio itself now calls validate_session
                await self.show_portfolio(update, context) # Pass update (which has query)
                
            elif data == "view_portfolio": # From TelegramAuthHandler's example buttons
                await self.show_portfolio(update, context)

            elif data == "market_making":
                await self.start_market_making(update, context, user_id)
                
            elif data == "execute_market_making":
                await self.execute_market_making_orders(update, context, user_id)
                
            elif data == "place_maker_order":
                await self.quick_maker_order(update, context, user_id)
                
            elif data == "refresh_profits":
                await self.show_profits(update, context)
                
            elif data == "check_rebates":
                await self.show_rebate_status(update, context, user_id)
                
            # Add all other existing callback handlers
            elif data == "quick_trade":
                await self.handle_quick_trade(update, context)
            elif data == "dca_strategy":
                await self.setup_dca_strategy(update, context, user_id)
            elif data == "grid_strategy":
                await self.setup_grid_strategy(update, context, user_id)
            elif data == "bridge_evm":
                await self.handle_bridge_evm(update, context, user_id)
            elif data == "hyperlend":
                await self.handle_hyperlend(update, context, user_id)
            elif data == "join_imc":
                await self.handle_join_imc(update, context, user_id)
            elif data == "volume_farming":
                await self.handle_volume_farming(update, context, user_id)
            elif data == "quick_buy_btc":
                await self.handle_quick_buy_btc(update, context, user_id)
            elif data == "quick_sell_btc":
                await self.handle_quick_sell_btc(update, context, user_id)
            elif data == "view_positions":
                await self.show_portfolio(update, context)
            elif data == "market_analysis":
                await self.show_market_analysis(update, context)
            elif data == "trading_settings":
                await self.show_trading_settings(update, context, user_id)
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def quick_maker_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Quick maker order placement"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        keyboard = [
            [InlineKeyboardButton("BTC Maker Orders", callback_data="maker_btc")],
            [InlineKeyboardButton("ETH Maker Orders", callback_data="maker_eth")],
            [InlineKeyboardButton("SOL Maker Orders", callback_data="maker_sol")],
            [InlineKeyboardButton("📊 Check Fee Tier", callback_data="check_fee_tier")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "🎯 **Quick Maker Orders**\n\n"
            "Place maker orders to earn rebates:\n\n"
            "💰 **Rebate Rates:**\n"
            "• 0.5%+ maker volume: -0.001%\n"
            "• 1.5%+ maker volume: -0.002%\n"
            "• 3%+ maker volume: -0.003%\n\n"
            "Choose an asset:",
            reply_markup=reply_markup
        )

    async def show_rebate_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Show current rebate status"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        try:
            session = self.user_sessions[user_id]
            trader = session["trader"]
            
            # Get REAL fee tier information
            fee_info = await trader.get_current_fee_tier()
            
            await update.callback_query.edit_message_text(
                f"📊 **Your Rebate Status**\n\n"
                f"🏆 **Current Tier:** {fee_info.get('tier', 'Bronze')}\n"
                f"📈 **14-day Volume:** ${fee_info.get('volume_14d', 0):,.0f}\n"
                f"🎯 **Maker Volume:** ${fee_info.get('maker_volume_14d', 0):,.0f}\n"
                f"📊 **Maker %:** {fee_info.get('maker_percentage', 0)*100:.2f}%\n\n"
                f"💰 **Current Rates:**\n"
                f"• Taker Fee: {fee_info.get('taker_fee', 0)*100:.3f}%\n"
                f"• Maker Fee: {fee_info.get('effective_maker_fee', 0)*100:.3f}%\n\n"
                f"🎁 **Rebate:** {abs(fee_info.get('rebate', 0))*100:.3f}% earned on maker orders!"
            )
            
        except Exception as e:
            logger.error(f"Rebate status error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error getting rebate status: {str(e)}")

    async def handle_deposit_vault(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle vault deposit using injected vault_manager"""
        user_id = update.effective_user.id
        
        if not self.vault_manager:
            await update.message.reply_text("❌ Vault system not available")
            return
        
        try:
            # Use injected vault_manager for deposit handling
            result = await self.vault_manager.handle_deposit(user_id, update, context)
            
            if result.get("status") == "success":
                # Update user stats in database if available
                if self.database:
                    try:
                        await self.database.update_user_vault_balance(
                            user_id, 
                            result.get('new_balance', 0)
                        )
                    except Exception as e:
                        logger.warning(f"Database update error: {e}")
                
                await update.message.reply_text(
                    f"✅ **Deposit Successful**\n\n"
                    f"💰 Amount: ${result.get('amount', 0):,.2f}\n"
                    f"📊 Your Vault Balance: ${result.get('new_balance', 0):,.2f}\n"
                    f"🎯 Expected Daily Return: {result.get('expected_daily_return', 0)*100:.2f}%\n\n"
                    f"Your funds are now earning from 4 alpha strategies!",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ **Deposit Failed**\n\n{result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"Vault deposit error: {e}")
            await update.message.reply_text(
                "💰 **Deposit to Vault**\n\n"
                "🚧 **System Error**\n\n"
                "Please try again later or contact support.",
                parse_mode='Markdown'
            )

    async def handle_vault_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle vault statistics using injected components"""
        user_id = update.effective_user.id
        
        if not self.vault_manager:
            await update.message.reply_text("❌ Vault system not available")
            return
        
        try:
            # Use injected vault_manager and database
            vault_stats = await self.vault_manager.get_vault_stats()
            
            user_stats = {}
            if self.database:
                try:
                    user_stats = await self.database.get_user_stats(user_id)
                except Exception as e:
                    logger.warning(f"Database error: {e}")
            
            stats_text = f"📊 **Vault Performance**\n\n"
            stats_text += f"💰 Total Value Locked: ${vault_stats.get('tvl', 0):,.0f}\n"
            stats_text += f"📈 Total Return: +{vault_stats.get('total_return', 0)*100:.1f}%\n"
            stats_text += f"📅 Active Days: {vault_stats.get('active_days', 0)}\n"
            stats_text += f"👥 Active Users: {vault_stats.get('active_users', 0)}\n\n"
            
            if user_stats:
                stats_text += f"**Your Stats:**\n"
                stats_text += f"• Your Balance: ${user_stats.get('vault_balance', 0):,.2f}\n"
                stats_text += f"• Your Profit: ${user_stats.get('total_profit', 0):+,.2f}\n"
                stats_text += f"• Your Return: +{user_stats.get('return_rate', 0)*100:.1f}%\n\n"
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Vault stats error: {e}")
            await update.message.reply_text(
                "📊 **Vault Performance**\n\n"
                "System temporarily unavailable. Please try again later.",
                parse_mode='Markdown'
            )

    async def handle_withdrawal_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle withdrawal request using injected vault_manager"""
        user_id = update.effective_user.id
        
        if not self.vault_manager:
            await update.message.reply_text("❌ Vault system not available")
            return
        
        try:
            # Use injected vault_manager for withdrawal handling
            result = await self.vault_manager.handle_withdrawal_request(user_id, update, context)
            
            if result.get("status") == "success":
                # Update user stats in database if available
                if self.database:
                    try:
                        await self.database.update_user_vault_balance(
                            user_id, 
                            result.get('remaining_balance', 0)
                        )
                    except Exception as e:
                        logger.warning(f"Database update error: {e}")
                
                await update.message.reply_text(
                    f"✅ **Withdrawal Requested**\n\n"
                    f"💰 Amount: ${result.get('amount', 0):,.2f}\n"
                    f"⏱️ Processing Time: {result.get('processing_time', '24 hours')}\n"
                    f"📊 Remaining Balance: ${result.get('remaining_balance', 0):,.2f}\n\n"
                    f"You'll receive a confirmation once processed.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ **Withdrawal Failed**\n\n{result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"Withdrawal error: {e}")
            await update.message.reply_text("❌ Error processing withdrawal request")

    async def execute_trade_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_params: Dict):
        """Execute trade order using injected trading_engine"""
        # user_id should be part of order_params or fetched from update if this is a direct command path
        # If called from a callback, query.from_user.id is the source.
        user_id = update.effective_user.id # Get user_id from the update object (message or query)

        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message) # Assuming it's from a callback
            return
        
        if not self.trading_engine:
            await update.callback_query.edit_message_text("❌ Trading engine not available")
            return
        
        try:
            session = self.user_sessions[user_id]
            exchange = session["exchange"]
            
            # Use injected trading_engine to execute order
            result = await self.trading_engine.place_order(
                exchange=exchange,
                coin=order_params.get('coin'),
                is_buy=order_params.get('is_buy'),
                sz=order_params.get('size'),
                limit_px=order_params.get('price'),
                order_type=order_params.get('order_type', 'Limit')
            )
            
            if result.get("status") == "success":
                # Update database if available
                if self.database:
                    try:
                        await self.database.record_trade(user_id, order_params, result)
                    except Exception as e:
                        logger.warning(f"Database record error: {e}")
                
                await update.callback_query.edit_message_text(
                    f"✅ **Order Placed Successfully**\n\n"
                    f"📊 Symbol: {order_params.get('coin')}\n"
                    f"🔄 Side: {'BUY' if order_params.get('is_buy') else 'SELL'}\n"
                    f"💰 Size: {order_params.get('size')}\n"
                    f"💲 Price: ${order_params.get('price')}\n"
                    f"📋 Order ID: {result.get('order_id', 'N/A')}\n\n"
                    f"Your order is now active on the exchange!",
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.edit_message_text(
                    f"❌ **Order Failed**\n\n{result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error executing trade: {str(e)}")

    async def handle_quick_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quick trade using injected trading_engine"""
        # This is likely a callback, so user_id from query
        user_id = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return

        if not self.trading_engine:
            await update.callback_query.edit_message_text("❌ Trading engine not available")
            return
        
        try:
            # Get current market prices using trading_engine
            market_data = await self.trading_engine.get_market_data()
            
            keyboard = [
                [InlineKeyboardButton(f"🚀 Buy BTC @ ${market_data.get('BTC', 0):,.0f}", 
                                    callback_data="quick_buy_BTC")],
                [InlineKeyboardButton(f"📉 Sell BTC @ ${market_data.get('BTC', 0):,.0f}", 
                                    callback_data="quick_sell_BTC")],
                [InlineKeyboardButton(f"🚀 Buy ETH @ ${market_data.get('ETH', 0):,.0f}", 
                                    callback_data="quick_buy_ETH")],
                [InlineKeyboardButton(f"📉 Sell ETH @ ${market_data.get('ETH', 0):,.0f}", 
                                    callback_data="quick_sell_ETH")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "⚡ **Quick Trade**\n\n"
                "Select your trade:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Quick trade error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error loading quick trade: {str(e)}")

    async def setup_grid_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Setup grid strategy using injected strategies"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        if not self.strategies or 'grid_trading' not in self.strategies:
            await update.callback_query.edit_message_text("❌ Grid trading strategy not available")
            return
        
        try:
            grid_strategy = self.strategies['grid_trading']
            
            # Check available balance using vault_manager
            available_balance = 0
            if self.vault_manager:
                try:
                    balance_info = await self.vault_manager.get_available_balance(user_id)
                    available_balance = balance_info.get('available', 0)
                except Exception as e:
                    logger.warning(f"Balance check error: {e}")
            
            keyboard = [
                [InlineKeyboardButton("🎯 Conservative Grid", callback_data="grid_conservative")],
                [InlineKeyboardButton("⚡ Aggressive Grid", callback_data="grid_aggressive")],
                [InlineKeyboardButton("⚙️ Custom Grid", callback_data="grid_custom")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                f"📊 **Grid Trading Strategy**\n\n"
                f"💰 Available Balance: ${available_balance:,.2f}\n\n"
                f"🎯 **Strategy Options:**\n"
                f"• Conservative: Lower risk, steady gains\n"
                f"• Aggressive: Higher risk, higher potential\n"
                f"• Custom: Set your own parameters\n\n"
                f"Choose your grid strategy:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Grid strategy setup error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error setting up grid strategy: {str(e)}")

    async def start_market_making(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Start market making strategy"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        try:
            # Check available balance using vault_manager
            available_balance = 0
            if self.vault_manager:
                try:
                    balance_info = await self.vault_manager.get_available_balance(user_id)
                    available_balance = balance_info.get('available', 0)
                except Exception as e:
                    logger.warning(f"Balance check error: {e}")
            
            keyboard = [
                [InlineKeyboardButton("🎯 Conservative MM", callback_data="mm_conservative")],
                [InlineKeyboardButton("⚡ Aggressive MM", callback_data="mm_aggressive")],
                [InlineKeyboardButton("🚀 Execute MM Orders", callback_data="execute_market_making")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                f"🎯 **Market Making Strategy**\n\n"
                f"💰 Available Balance: ${available_balance:,.2f}\n\n"
                f"📊 **Benefits:**\n"
                f"• Earn maker rebates (-0.001% to -0.003%)\n"
                f"• Capture bid-ask spread\n"
                f"• Automated order management\n\n"
                f"Choose your market making style:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Market making setup error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error setting up market making: {str(e)}")

    async def execute_market_making_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Execute market making orders"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        if not self.trading_engine:
            await update.callback_query.edit_message_text("❌ Trading engine not available")
            return
        
        try:
            session = self.user_sessions[user_id]
            exchange = session["exchange"]
            
            # Execute market making strategy using trading_engine
            result = await self.trading_engine.execute_market_making(
                exchange=exchange,
                symbol="BTC",
                capital_allocation=1000,  # Default allocation
                spread_percentage=0.1
            )
            
            if result.get("status") == "success":
                orders_placed = result.get("orders_placed", 0)
                total_volume = result.get("total_volume", 0)
                
                await update.callback_query.edit_message_text(
                    f"✅ **Market Making Active**\n\n"
                    f"📊 Orders Placed: {orders_placed}\n"
                    f"💰 Total Volume: ${total_volume:,.2f}\n"
                    f"🎯 Expected Daily Rebates: ${result.get('expected_rebates', 0):.4f}\n\n"
                    f"🤖 Strategy is now running automatically!"
                )
            else:
                await update.callback_query.edit_message_text(
                    f"❌ **Market Making Failed**\n\n{result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"Market making execution error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error executing market making: {str(e)}")

    async def setup_dca_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Setup DCA strategy"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        if not self.strategies or 'automated_trading' not in self.strategies: # Assuming DCA is part of auto_trading
            await update.callback_query.edit_message_text("❌ DCA strategy not available")
            return
        
        try:
            keyboard = [
                [InlineKeyboardButton("🟢 BTC DCA", callback_data="dca_btc")],
                [InlineKeyboardButton("🔵 ETH DCA", callback_data="dca_eth")],
                [InlineKeyboardButton("🟣 SOL DCA", callback_data="dca_sol")],
                [InlineKeyboardButton("⚙️ Custom DCA", callback_data="dca_custom")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "🤖 **Dollar Cost Averaging**\n\n"
                "🎯 **Strategy Benefits:**\n"
                "• Reduce volatility impact\n"
                "• Automated buying at intervals\n"
                "• Lower average entry price\n\n"
                "Choose your DCA asset:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"DCA setup error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error setting up DCA: {str(e)}")

    async def handle_bridge_evm(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Handle bridging to EVM"""
        # This action might not require an active Hyperliquid session, but good to be consistent if it does
        # is_valid, error_message = self.auth_handler.validate_session(user_id)
        # if not is_valid:
        # await update.callback_query.edit_message_text(error_message)
        # return
        try:
            keyboard = [
                [InlineKeyboardButton("🔄 Bridge USDC", callback_data="bridge_usdc")],
                [InlineKeyboardButton("💰 Bridge ETH", callback_data="bridge_eth")],
                [InlineKeyboardButton("📊 Bridge Status", callback_data="check_bridge_status")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "🌉 **Bridge to HyperEVM**\n\n"
                "🔄 **Available Bridges:**\n"
                "• USDC: Instant bridging\n"
                "• ETH: 5-minute confirmation\n"
                "• Low fees: ~$0.10\n\n"
                "Choose asset to bridge:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Error: {str(e)}")

    async def handle_hyperlend(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Handle HyperLend operations"""
        # Similar to bridge, may not need active HL session for info display
        try:
            keyboard = [
                [InlineKeyboardButton("💰 Lend USDC", callback_data="lend_usdc")],
                [InlineKeyboardButton("📈 Borrow Against Collateral", callback_data="borrow_collateral")],
                [InlineKeyboardButton("📊 Lending Rates", callback_data="lending_rates")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "💰 **HyperLend Protocol**\n\n"
                "📈 **Current Rates:**\n"
                "• USDC Lending: 8.5% APY\n"
                "• ETH Collateral: 75% LTV\n"
                "• BTC Collateral: 80% LTV\n\n"
                "Choose your action:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Error: {str(e)}")

    async def handle_join_imc(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Handle joining IMC pool"""
        # Similar to bridge, may not need active HL session for info display
        try:
            keyboard = [
                [InlineKeyboardButton("🎯 Join Tier 1 ($1K)", callback_data="imc_tier1")],
                [InlineKeyboardButton("🚀 Join Tier 2 ($5K)", callback_data="imc_tier2")],
                [InlineKeyboardButton("💎 Join Tier 3 ($10K)", callback_data="imc_tier3")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "🌱 **Seedify IMC Pool**\n\n"
                "💰 **Investment Tiers:**\n"
                "• Tier 1: $1,000 minimum\n"
                "• Tier 2: $5,000 minimum\n"
                "• Tier 3: $10,000 minimum\n\n"
                "🎁 **Benefits:**\n"
                "• Access to exclusive launches\n"
                "• Revenue sharing from volume\n"
                "• Professional management\n\n"
                "Choose your tier:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Error: {str(e)}")

    async def handle_quick_buy_btc(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Handle quick BTC buy"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        if not self.trading_engine:
            await update.callback_query.edit_message_text("❌ Trading engine not available")
            return
        
        try:
            session = self.user_sessions[user_id]
            exchange = session["exchange"]
            
            # Get current BTC price
            market_data = await self.trading_engine.get_market_data()
            btc_price = market_data.get('BTC', 43000)
            
            # Execute quick buy (0.01 BTC default)
            order_params = {
                'coin': 'BTC',
                'is_buy': True,
                'size': 0.01,
                'price': btc_price * 1.001,  # Slight premium for immediate fill
                'order_type': 'Limit'
            }
            
            await self.execute_trade_order(update, context, order_params)
            
        except Exception as e:
            logger.error(f"Quick BTC buy error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error buying BTC: {str(e)}")

    async def handle_quick_sell_btc(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Handle quick BTC sell"""
        is_valid, error_message = self.auth_handler.validate_session(user_id)
        if not is_valid:
            await update.callback_query.edit_message_text(error_message)
            return
        
        if not self.trading_engine:
            await update.callback_query.edit_message_text("❌ Trading engine not available")
            return
        
        try:
            session = self.user_sessions[user_id]
            exchange = session["exchange"]
            
            # Get current BTC price
            market_data = await self.trading_engine.get_market_data()
            btc_price = market_data.get('BTC', 43000)
            
            # Execute quick sell (0.01 BTC default)
            order_params = {
                'coin': 'BTC',
                'is_buy': False,
                'size': 0.01,
                'price': btc_price * 0.999,  # Slight discount for immediate fill
                'order_type': 'Limit'
            }
            
            await self.execute_trade_order(update, context, order_params)
            
        except Exception as e:
            logger.error(f"Quick BTC sell error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error selling BTC: {str(e)}")

    async def show_market_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show market analysis"""
        # This is likely a callback, so user_id from query
        user_id = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
        # Market analysis might be general, or user-specific if settings affect it.
        # Assuming general for now, so no session validation needed unless it becomes personalized.
        try:
            if self.trading_engine:
                market_data = await self.trading_engine.get_market_data()
                analysis = await self.trading_engine.get_market_analysis()
            else:
                # Fallback static data
                market_data = {'BTC': 43250, 'ETH': 2680, 'SOL': 98.5}
                analysis = {'trend': 'bullish', 'volatility': 'moderate'}
            
            keyboard = [
                [InlineKeyboardButton("📊 Technical Analysis", callback_data="technical_analysis")],
                [InlineKeyboardButton("📈 Price Alerts", callback_data="price_alerts")],
                [InlineKeyboardButton("🔄 Refresh Data", callback_data="refresh_analysis")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                f"📊 **Market Analysis**\n\n"
                f"💰 **Current Prices:**\n"
                f"• BTC: ${market_data.get('BTC', 0):,.0f}\n"
                f"• ETH: ${market_data.get('ETH', 0):,.0f}\n"
                f"• SOL: ${market_data.get('SOL', 0):,.1f}\n\n"
                f"📈 **Market Trend:** {analysis.get('trend', 'Unknown').title()}\n"
                f"📊 **Volatility:** {analysis.get('volatility', 'Unknown').title()}\n\n"
                f"🎯 **Recommendation:** {analysis.get('recommendation', 'Hold positions')}\n",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Market analysis error: {e}")
            await update.callback_query.edit_message_text(f"❌ Error loading analysis: {str(e)}")

    async def show_trading_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int): # user_id passed as arg
        """Show trading settings"""
        # is_valid, error_message = self.auth_handler.validate_session(user_id) # If settings are per-user and require auth
        # if not is_valid:
            # await update.callback_query.edit_message_text(error_message)
            # return
        try:
            keyboard = [
                [InlineKeyboardButton("⚙️ Risk Management", callback_data="risk_settings")],
                [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")],
                [InlineKeyboardButton("💰 Default Order Size", callback_data="order_size_settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "⚙️ **Trading Settings**\n\n"
                "🛡️ **Risk Management:**\n"
                "• Max Position Size: 10%\n"
                "• Stop Loss: 5%\n"
                "• Daily Loss Limit: 2%\n\n"
                "🔔 **Notifications:**\n"
                "• Trade Confirmations: ✅\n"
                "• Price Alerts: ✅\n"
                "• Daily Reports: ✅\n\n"
                "Choose setting to modify:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ Error: {str(e)}")

    async def show_live_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show live trading interface"""
        user_id = update.effective_user.id # From message
        
        # Check session status but don't block the informational part if not connected
        is_connected, _ = self.auth_handler.validate_session(user_id) # Use a softer check
        
        if not is_connected: # Show generic info if not connected
            await update.message.reply_text(
                "📈 **Live Trading**\n\n"
                "To access live trading, you need to connect your wallet first.\n\n"
                "Use /connect YOUR_PRIVATE_KEY to get started.\n\n"
                "**Live Trading Features:**\n"
                "• Real-time price monitoring\n"
                "• One-click buy/sell orders\n"
                "• Advanced order types\n"
                "• Risk management tools\n"
                "• Profit/loss tracking\n\n"
                "Connect your wallet to unlock these features!",
                parse_mode='Markdown'
            )
            return
        
        # User is connected, show trading interface
        keyboard = [
            [InlineKeyboardButton("🚀 Quick Buy BTC", callback_data="quick_buy_btc")],
            [InlineKeyboardButton("📉 Quick Sell BTC", callback_data="quick_sell_btc")],
            [InlineKeyboardButton("📊 View Positions", callback_data="view_positions")],
            [InlineKeyboardButton("📈 Market Analysis", callback_data="market_analysis")],
            [InlineKeyboardButton("⚙️ Trading Settings", callback_data="trading_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # Get real-time data if trading_engine available
            if self.trading_engine:
                market_data = await self.trading_engine.get_market_data()
                btc_price = market_data.get('BTC', 43250)
                eth_price = market_data.get('ETH', 2680)
                sol_price = market_data.get('SOL', 98.5)
            else:
                btc_price, eth_price, sol_price = 43250, 2680, 98.5
            
            await update.message.reply_text(
                f"📈 **Live Trading Interface**\n\n"
                f"🔥 **Real-time Prices:**\n"
                f"• BTC: ${btc_price:,.0f}\n"
                f"• ETH: ${eth_price:,.0f}\n"
                f"• SOL: ${sol_price:,.1f}\n\n"
                f"💰 **Your Account:**\n"
                f"• Status: Connected ✅\n"
                f"• Trading Engine: {'Active' if self.trading_engine else 'Inactive'}\n\n"
                f"Choose a trading action:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Live trading interface error: {e}")
            await update.message.reply_text(
                "📈 **Live Trading Interface**\n\n❌ Error loading interface. Please try again.",
                parse_mode='Markdown'
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = """
📚 **Aptos Alpha Bot - Help**

/start - Start the bot and see main menu
/connect - Connect your Aptos wallet
/deposit - Deposit APT to the vault
/stats - View vault performance stats
/withdraw - Withdraw from the vault
/aptos - Access Aptos DeFi features
/seedify - Explore Seedify IMC pools
/strategies - Manage your trading strategies
/profits - View your profit analytics
/help - Show this help message

🔗 **Links:**
- [Aptos Documentation](https://aptos.dev)
- [Telegram Group](https://t.me/aptos_alpha_bot)
- [Twitter](https://twitter.com/aptos_alpha_bot)

For support, contact @AptosAlphaBotSupport
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown'
        )

    async def get_real_stats(self, client, address):
        """Get real stats from Aptos blockchain"""
        try:
            # Get APT balance
            apt_balance = await client.account_balance(address)
            account_value = apt_balance / 100_000_000
            
            # Get transaction history (simplified)
            transactions = await client.account_transactions(address, limit=100)
            
            # Calculate volume from recent transactions
            volume_24h = 0
            trades_count = len(transactions)
            
            # In a real implementation, you'd parse transaction data for trading volume
            # For now, estimate based on transaction count and average size
            if trades_count > 0:
                volume_24h = trades_count * account_value * 0.1  # Rough estimate
            
            return {
                'account_value': account_value,
                'volume_24h': volume_24h,
                'trades_count': trades_count
            }
        except Exception as e:
            logger.error(f"Error getting real stats: {e}")
            return {
                'account_value': 0,
                'volume_24h': 0,
                'trades_count': 0
            }

    async def vault_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fetch vault info from Aptos blockchain"""
        vault_address = self.main_config.get("vault_address")
        if not vault_address:
            await update.message.reply_text("Vault address not configured.")
            return
        
        try:
            # Get vault info from Aptos
            user_id = update.effective_user.id
            session = self.user_sessions.get(user_id)
            if not session:
                await update.message.reply_text("Please connect your wallet first with /connect")
                return
                
            client = session["client"]
            apt_balance = await client.account_balance(vault_address)
            account_value = apt_balance / 100_000_000
            
            await update.message.reply_text(
                f"Vault Address: {vault_address}\n"
                f"Vault APT Balance: {account_value:,.8f} APT"
            )
        except Exception as e:
            await update.message.reply_text(f"Error fetching vault info: {e}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user stats from Aptos"""
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id)
        if not session:
            await update.message.reply_text("Please connect your wallet first with /connect")
            return
            
        client = session["client"]
        address = session["address"]
        stats = await self.get_real_stats(client, address)
        
        await update.message.reply_text(
            f"Account Value: {stats['account_value']:,.8f} APT\n"
            f"24h Volume (estimated): {stats['volume_24h']:,.2f} APT\n"
            f"Total Transactions: {stats['trades_count']}"
        )

    async def _get_account_value(self, client: RestClient, address: str) -> float:
        """Helper to get account value from Aptos blockchain."""
        try:
            apt_balance = await client.account_balance(address)
            return apt_balance / 100_000_000  # Convert from octas to APT
        except Exception as e:
            self.logger.error(f"Failed to get account value for {address}: {e}")
            return 0.0

    # Ensure this method is present if called by other parts of the bot
    async def run(self):
        logger.info("Telegram bot polling started...")
        # If self.app is Application instance
        await self.app.initialize() # Initialize handlers, etc.
        await self.app.start()
        await self.app.updater.start_polling() # Start polling
        # Keep it running, or integrate with main bot's loop
        # For example, if main bot has its own loop:
        # while not self.app.updater.is_idle: # Or similar check
        #    await asyncio.sleep(1)

    async def stop(self):
        logger.info("Stopping Telegram bot...")
        if self.app and self.app.updater:
            await self.app.updater.stop()
        if self.app:
            await self.app.stop()
            await self.app.shutdown()

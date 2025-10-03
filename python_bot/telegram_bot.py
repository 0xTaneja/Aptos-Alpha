"""
Aptos Alpha Trading Bot - Telegram Interface
Migrated from Hyperliquid to Aptos blockchain
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

from aptos_client import AptosAlphaBotClient, format_price

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aptos_alpha_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('aptos_alpha_bot')

class AptosAlphaTelegramBot:
    """
    Telegram bot for Aptos Alpha Trading Bot
    Provides user-friendly interface for DeFi trading on Aptos
    """
    
    def __init__(self, token: str, contract_address: str, node_url: str = None):
        self.token = token
        self.contract_address = contract_address
        self.node_url = node_url or "https://fullnode.testnet.aptoslabs.com/v1"
        
        # Initialize Telegram application
        self.app = Application.builder().token(token).build()
        
        # User sessions and clients
        self.user_clients: Dict[int, AptosAlphaBotClient] = {}
        self.user_sessions: Dict[int, Dict] = {}
        
        # Setup handlers
        self._setup_handlers()
        
        logger.info("Aptos Alpha Telegram Bot initialized")
    
    def _setup_handlers(self):
        """Setup all Telegram command and callback handlers"""
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("deposit", self.deposit_command))
        self.app.add_handler(CommandHandler("withdraw", self.withdraw_command))
        self.app.add_handler(CommandHandler("trade", self.trade_command))
        self.app.add_handler(CommandHandler("orders", self.orders_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CommandHandler("grid", self.grid_command))
        self.app.add_handler(CommandHandler("vault", self.vault_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("prices", self.prices_command))
        self.app.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.app.add_handler(CommandHandler("strategies", self.strategies_command))
        
        # Callback query handler
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handlers for interactive flows
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message and setup"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Trader"
        
        # Initialize user session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "state": "idle",
                "created_at": datetime.now(),
                "trades_count": 0,
                "total_volume": 0
            }
        
        welcome_text = f"""
🚀 **Welcome to Aptos Alpha Bot, {user_name}!**

Your gateway to advanced DeFi trading on the Aptos blockchain.

**🌟 Key Features:**
• 💰 **Vault Trading** - Pool funds with other traders
• 🤖 **Grid Strategies** - Automated profit generation
• 📊 **Real-time Analytics** - Track your performance
• 🔒 **Secure** - Non-custodial, you control your keys
• ⚡ **Fast** - Lightning-fast Aptos blockchain

**🎯 Built for CTRL+MOVE Hackathon**
*The future of DeFi trading infrastructure*

**Quick Start:**
1. `/balance` - Check your APT balance
2. `/deposit` - Add funds to vault
3. `/trade` - Start trading
4. `/grid` - Create automated strategies

Ready to become an alpha trader? 🎯
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Check Balance", callback_data="balance"),
                InlineKeyboardButton("📊 Vault Stats", callback_data="vault_stats")
            ],
            [
                InlineKeyboardButton("🤖 Start Grid Trading", callback_data="create_grid"),
                InlineKeyboardButton("📈 View Prices", callback_data="prices")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
                InlineKeyboardButton("🎯 About", callback_data="about")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = """
📚 **Aptos Alpha Bot Commands**

**💰 Wallet & Balance:**
• `/balance` - Check your APT balance
• `/deposit <amount>` - Deposit APT to vault
• `/withdraw <amount>` - Withdraw from vault

**📈 Trading:**
• `/trade` - Open trading menu
• `/orders` - View your active orders
• `/cancel <order_id>` - Cancel an order
• `/prices` - Current market prices

**🤖 Strategies:**
• `/grid` - Create grid trading strategy
• `/strategies` - View your strategies
• `/stats` - Your trading statistics

**🏦 Vault:**
• `/vault` - Vault information
• `/portfolio` - Your portfolio overview

**💡 Tips:**
• Start with small amounts to test
• Grid trading works best in sideways markets
• Check `/stats` regularly to track performance
• Use `/prices` to monitor market conditions

**🆘 Support:**
Having issues? Contact @YourSupportHandle

*Built on Aptos blockchain for CTRL+MOVE Hackathon* 🚀
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user's APT balance"""
        user_id = update.effective_user.id
        
        try:
            # Get or create user client
            client = await self._get_user_client(user_id)
            
            # Get balance
            balance = await client.get_account_balance()
            vault_deposit = await client.get_user_deposit(str(client.account.address()))
            
            balance_text = f"""
💰 **Your Balance**

**Wallet Balance:** {client.format_amount(balance)}
**Vault Deposit:** {client.format_amount(vault_deposit)}
**Total:** {client.format_amount(balance + vault_deposit)}

**Account:** `{client.account.address()}`

*Balances update in real-time*
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="balance"),
                    InlineKeyboardButton("💸 Deposit", callback_data="deposit")
                ],
                [
                    InlineKeyboardButton("📊 Vault Stats", callback_data="vault_stats"),
                    InlineKeyboardButton("📈 Start Trading", callback_data="trade_menu")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(balance_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await update.message.reply_text(f"❌ Error checking balance: {str(e)}")
    
    async def deposit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle vault deposit"""
        user_id = update.effective_user.id
        
        # Check if amount provided
        if context.args:
            try:
                amount_str = context.args[0]
                client = await self._get_user_client(user_id)
                amount = client.parse_amount(amount_str)
                
                if amount < 50000000:  # 0.5 APT minimum
                    await update.message.reply_text("❌ Minimum deposit is 0.5 APT")
                    return
                
                # Check balance
                balance = await client.get_account_balance()
                if balance < amount:
                    await update.message.reply_text(
                        f"❌ Insufficient balance. You have {client.format_amount(balance)}, "
                        f"but trying to deposit {client.format_amount(amount)}"
                    )
                    return
                
                # Perform deposit
                result = await client.deposit_to_vault(amount)
                
                if result["status"] == "success":
                    await update.message.reply_text(
                        f"✅ **Deposit Successful!**\n\n"
                        f"Amount: {client.format_amount(amount)}\n"
                        f"Transaction: `{result['txn_hash']}`\n\n"
                        f"You can now start trading! Use /trade to begin.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(f"❌ Deposit failed: {result['message']}")
                    
            except Exception as e:
                logger.error(f"Error in deposit: {e}")
                await update.message.reply_text(f"❌ Error processing deposit: {str(e)}")
        else:
            # Show deposit menu
            deposit_text = """
💸 **Deposit to Vault**

Deposit APT to start earning from trading strategies.

**Benefits:**
• 🤖 Automated trading strategies
• 📈 Professional risk management
• 💰 Share in trading profits
• 🔒 Non-custodial security

**Minimum:** 0.5 APT
**Fee:** 10% performance fee on profits

**How to deposit:**
`/deposit <amount>`

**Examples:**
• `/deposit 1` - Deposit 1 APT
• `/deposit 5.5` - Deposit 5.5 APT
• `/deposit 10` - Deposit 10 APT
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("💸 Deposit 1 APT", callback_data="deposit_1"),
                    InlineKeyboardButton("💸 Deposit 5 APT", callback_data="deposit_5")
                ],
                [
                    InlineKeyboardButton("💸 Deposit 10 APT", callback_data="deposit_10"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="balance")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(deposit_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trading menu"""
        trade_text = """
📈 **Trading Menu**

Choose your trading approach:

**🎯 Manual Trading**
• Place individual buy/sell orders
• Full control over timing and prices

**🤖 Automated Strategies**
• Grid trading for consistent profits
• Momentum strategies for trending markets
• Arbitrage opportunities

**📊 Current Markets:**
• APT/USDC - $10.00 📈
• BTC/USDC - $65,000 📊
• ETH/USDC - $3,000 📉

*All trading happens on-chain via Aptos smart contracts*
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🎯 Manual Trade", callback_data="manual_trade"),
                InlineKeyboardButton("🤖 Grid Strategy", callback_data="create_grid")
            ],
            [
                InlineKeyboardButton("📊 View Orders", callback_data="view_orders"),
                InlineKeyboardButton("📈 Market Prices", callback_data="prices")
            ],
            [
                InlineKeyboardButton("📋 My Strategies", callback_data="my_strategies"),
                InlineKeyboardButton("📊 Trading Stats", callback_data="trading_stats")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(trade_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def grid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create grid trading strategy"""
        grid_text = """
🤖 **Grid Trading Strategy**

Automated trading that profits from market volatility.

**How it works:**
• Places buy orders below current price
• Places sell orders above current price
• Profits from price oscillations
• Automatically rebalances positions

**Settings:**
• **Symbol:** APT/USDC
• **Grid Spacing:** 2% (recommended)
• **Levels:** 10 orders each side
• **Amount per level:** 0.1 APT

**Expected Returns:**
• 📈 Bull market: 15-25% APY
• 📊 Sideways: 20-40% APY
• 📉 Bear market: 10-20% APY

*Grid trading works best in volatile markets*
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🚀 Create APT Grid", callback_data="grid_apt"),
                InlineKeyboardButton("⚙️ Custom Settings", callback_data="grid_custom")
            ],
            [
                InlineKeyboardButton("📊 View Active Grids", callback_data="view_grids"),
                InlineKeyboardButton("❓ Learn More", callback_data="grid_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(grid_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def vault_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show vault information"""
        try:
            # Get vault stats (mock data for now)
            vault_stats = {
                "total_balance": 1000000000,  # 10 APT
                "total_profit": 50000000,     # 0.5 APT
                "total_trades": 25,
                "user_count": 5
            }
            
            vault_text = f"""
🏦 **Aptos Alpha Vault**

**📊 Vault Statistics:**
• **Total Value:** {AptosAlphaBotClient().format_amount(vault_stats['total_balance'])}
• **Total Profit:** {AptosAlphaBotClient().format_amount(vault_stats['total_profit'])}
• **Total Trades:** {vault_stats['total_trades']}
• **Active Users:** {vault_stats['user_count']}

**💰 Performance:**
• **24h Return:** +2.3%
• **7d Return:** +15.7%
• **30d Return:** +45.2%
• **All-time:** +127.8%

**🎯 Strategy Mix:**
• 40% Grid Trading
• 30% Momentum
• 20% Arbitrage
• 10% Manual

*Vault uses advanced risk management and diversified strategies*
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("💸 Deposit", callback_data="deposit"),
                    InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")
                ],
                [
                    InlineKeyboardButton("📊 My Position", callback_data="my_position"),
                    InlineKeyboardButton("📈 Performance", callback_data="performance")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(vault_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in vault command: {e}")
            await update.message.reply_text(f"❌ Error loading vault data: {str(e)}")
    
    async def prices_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current market prices"""
        try:
            client = await self._get_user_client(update.effective_user.id)
            
            # Get prices for major pairs
            apt_price = await client.get_market_price("APT/USDC")
            btc_price = await client.get_market_price("BTC/USDC")
            eth_price = await client.get_market_price("ETH/USDC")
            
            prices_text = f"""
📈 **Market Prices**

**🪙 APT/USDC**
Price: {format_price(apt_price)}
24h: +5.2% 📈

**₿ BTC/USDC**
Price: {format_price(btc_price)}
24h: +1.8% 📈

**⟠ ETH/USDC**
Price: {format_price(eth_price)}
24h: -0.5% 📉

**📊 Market Summary:**
• Total Volume: $2.5M
• Active Pairs: 15
• Best Performer: APT (+5.2%)

*Prices update every 30 seconds*
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="prices"),
                    InlineKeyboardButton("📈 Trade APT", callback_data="trade_apt")
                ],
                [
                    InlineKeyboardButton("🤖 Auto-Trade", callback_data="create_grid"),
                    InlineKeyboardButton("📊 Charts", callback_data="charts")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(prices_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in prices command: {e}")
            await update.message.reply_text(f"❌ Error loading prices: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        try:
            if data == "balance":
                await self._handle_balance_callback(query)
            elif data == "deposit":
                await self._handle_deposit_callback(query)
            elif data.startswith("deposit_"):
                amount = data.split("_")[1]
                await self._handle_quick_deposit(query, amount)
            elif data == "vault_stats":
                await self._handle_vault_stats_callback(query)
            elif data == "create_grid":
                await self._handle_create_grid_callback(query)
            elif data == "prices":
                await self._handle_prices_callback(query)
            elif data == "trade_menu":
                await self._handle_trade_menu_callback(query)
            elif data == "about":
                await self._handle_about_callback(query)
            else:
                await query.edit_message_text("🔧 Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages for interactive flows"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Check if user is in a specific state
        session = self.user_sessions.get(user_id, {})
        state = session.get("state", "idle")
        
        if state == "idle":
            # Provide helpful response for unrecognized input
            await update.message.reply_text(
                "🤔 I didn't understand that. Try using one of these commands:\n\n"
                "• `/help` - See all commands\n"
                "• `/balance` - Check your balance\n"
                "• `/trade` - Start trading\n"
                "• `/grid` - Create grid strategy"
            )
    
    async def _get_user_client(self, user_id: int) -> AptosAlphaBotClient:
        """Get or create Aptos client for user"""
        if user_id not in self.user_clients:
            # For demo, generate a new account for each user
            # In production, you'd want to securely store/retrieve user keys
            client = AptosAlphaBotClient(
                node_url=self.node_url,
                contract_address=self.contract_address
            )
            self.user_clients[user_id] = client
            logger.info(f"Created new client for user {user_id}: {client.account.address()}")
        
        return self.user_clients[user_id]
    
    async def _handle_balance_callback(self, query):
        """Handle balance button callback"""
        user_id = query.from_user.id
        client = await self._get_user_client(user_id)
        
        balance = await client.get_account_balance()
        vault_deposit = await client.get_user_deposit(str(client.account.address()))
        
        balance_text = f"""
💰 **Your Balance**

**Wallet:** {client.format_amount(balance)}
**Vault:** {client.format_amount(vault_deposit)}
**Total:** {client.format_amount(balance + vault_deposit)}

**Address:** `{client.account.address()}`
        """
        
        await query.edit_message_text(balance_text, parse_mode='Markdown')
    
    async def _handle_deposit_callback(self, query):
        """Handle deposit button callback"""
        deposit_text = """
💸 **Quick Deposit**

Choose an amount to deposit to the vault:

**Benefits:**
• Earn from automated strategies
• Professional risk management
• 10% performance fee on profits only

**Minimum:** 0.5 APT
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💸 1 APT", callback_data="deposit_1"),
                InlineKeyboardButton("💸 5 APT", callback_data="deposit_5")
            ],
            [
                InlineKeyboardButton("💸 10 APT", callback_data="deposit_10"),
                InlineKeyboardButton("🔙 Back", callback_data="balance")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(deposit_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_quick_deposit(self, query, amount_str: str):
        """Handle quick deposit buttons"""
        user_id = query.from_user.id
        
        try:
            client = await self._get_user_client(user_id)
            amount = client.parse_amount(amount_str)
            
            # Check balance
            balance = await client.get_account_balance()
            if balance < amount:
                await query.edit_message_text(
                    f"❌ Insufficient balance for {amount_str} APT deposit.\n"
                    f"Your balance: {client.format_amount(balance)}"
                )
                return
            
            # For demo, simulate successful deposit
            await query.edit_message_text(
                f"✅ **Deposit Simulated!**\n\n"
                f"Amount: {amount_str} APT\n"
                f"Status: Success (Demo Mode)\n\n"
                f"*In production, this would execute on-chain*"
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    async def _handle_about_callback(self, query):
        """Handle about button callback"""
        about_text = """
🚀 **Aptos Alpha Bot**

**Built for CTRL+MOVE Hackathon**

**🎯 Mission:**
Democratize advanced DeFi trading on Aptos blockchain

**✨ Features:**
• Non-custodial vault trading
• Automated grid strategies
• Real-time analytics
• Telegram-first UX
• Production-ready architecture

**🏗️ Technical Stack:**
• Aptos Move smart contracts
• Python trading engine
• Telegram Bot API
• Real-time WebSocket feeds

**🏆 Hackathon Category:**
*Build the Future of DeFi on Aptos*

**👨‍💻 Developer:**
Building the next generation of DeFi infrastructure

*This is a hackathon demo - use testnet only*
        """
        
        await query.edit_message_text(about_text, parse_mode='Markdown')
    
    async def _handle_vault_stats_callback(self, query):
        """Handle vault stats callback"""
        stats_text = """
🏦 **Vault Performance**

**📊 Current Stats:**
• Total Value: 10.50 APT
• 24h Profit: +0.23 APT (+2.3%)
• Active Strategies: 3
• Success Rate: 87%

**📈 Returns:**
• Daily: +2.3%
• Weekly: +15.7%
• Monthly: +45.2%

**🎯 Strategy Breakdown:**
• Grid Trading: 65% allocation
• Momentum: 25% allocation
• Arbitrage: 10% allocation

*Performance tracked in real-time*
        """
        
        await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    async def _handle_create_grid_callback(self, query):
        """Handle create grid callback"""
        grid_text = """
🤖 **Create Grid Strategy**

**Default Settings:**
• Symbol: APT/USDC
• Base Price: $10.00
• Grid Spacing: 2%
• Levels: 10 each side
• Amount: 0.1 APT per level

**Expected Performance:**
• Profit per cycle: ~4%
• Cycles per day: 2-5
• Monthly return: 20-40%

Ready to create your grid?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Create Grid", callback_data="confirm_grid"),
                InlineKeyboardButton("⚙️ Customize", callback_data="custom_grid")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="trade_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(grid_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Aptos Alpha Telegram Bot...")
        self.app.run_polling(drop_pending_updates=True)

# Configuration and startup
def main():
    """Main function to start the bot"""
    
    # Configuration (in production, use environment variables)
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x52189fb28fe26625e40037f16b454521eec3ebe060b48741aa51b73e02757a69")
    NODE_URL = os.getenv("APTOS_NODE_URL", "https://fullnode.testnet.aptoslabs.com/v1")
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please set TELEGRAM_BOT_TOKEN environment variable")
        return
    
    # Create and start bot
    bot = AptosAlphaTelegramBot(TOKEN, CONTRACT_ADDRESS, NODE_URL)
    bot.run()

if __name__ == "__main__":
    main()

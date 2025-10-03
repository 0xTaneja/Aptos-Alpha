from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)

class OnboardingHandler:
    """
    Handles the Aptos onboarding flow for new users:
    - Welcome tutorial
    - Aptos agent wallet creation guide
    - APT funding instructions (with QR code)
    - First Aptos trade walkthrough
    - Safety guidelines
    """

    def __init__(self, wallet_manager):
        self.wallet_manager = wallet_manager

    async def start_onboarding(self, update: Update, context: CallbackContext):
        """Entry point for onboarding tutorial."""
        welcome_msg = (
            "👋 *Welcome to Aptos Alpha Bot!*\n\n"
            "This quick tutorial will help you:\n"
            "1️⃣ Create your secure Aptos agent wallet\n"
            "2️⃣ Fund your wallet with APT (with QR code)\n"
            "3️⃣ Place your first Aptos trade\n"
            "4️⃣ Learn safety best practices\n\n"
            "Ready to get started?"
        )
        keyboard = [
            [InlineKeyboardButton("🚀 Start Tutorial", callback_data="onboard_step_1")],
            [InlineKeyboardButton("Skip Tutorial", callback_data="onboard_skip")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def handle_onboarding_callback(self, update: Update, context: CallbackContext):
        """Handles onboarding steps via callback queries."""
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id

        if data == "onboard_step_1":
            await self.agent_wallet_guide(query, context)
        elif data == "onboard_step_2":
            await self.funding_instructions(query, context)
        elif data == "onboard_step_3":
            await self.first_trade_walkthrough(query, context)
        elif data == "onboard_step_4":
            await self.safety_guidelines(query, context)
        elif data == "onboard_complete":
            await self.onboarding_complete(query, context)
        elif data == "onboard_skip":
            await query.edit_message_text("You can access the tutorial anytime with /tutorial.", parse_mode='Markdown')
        else:
            await query.answer("Unknown onboarding step.")

    async def agent_wallet_guide(self, query, context):
        """Guide users through agent wallet creation"""
        msg = (
            "🔐 *Step 1: Create Your Aptos Agent Wallet*\n\n"
            "Aptos agent wallets let you trade securely without exposing your private key.\n\n"
            "**How it works:**\n"
            "• The bot creates a dedicated Aptos trading wallet for you\n"
            "• You fund it with APT for trading\n"
            "• All trades happen through this secure Aptos wallet\n"
            "• You maintain full control of your funds\n\n"
            "Ready to create your Aptos wallet?"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Create Aptos Agent Wallet", callback_data="create_agent")],
            [InlineKeyboardButton("❓ Learn More", callback_data="agent_wallet_info")],
            [InlineKeyboardButton("Next: Funding →", callback_data="onboard_step_2")]
        ]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def funding_instructions(self, query, context):
        """Show detailed funding instructions with QR code"""
        user_id = query.from_user.id
        user_wallet = await self.wallet_manager.get_user_wallet(user_id) if self.wallet_manager else None
        address = user_wallet['address'] if user_wallet else "0x1234...abcd"

        msg = (
            "💰 *Step 2: Fund Your Aptos Agent Wallet*\n\n"
            f"**Your Aptos Agent Wallet Address:**\n`{address}`\n\n"
            "**Funding Instructions:**\n"
            "• Send APT (minimum 10 APT) to the address above\n"
            "• Use *Aptos Mainnet* network only\n"
            "• Funding typically takes 1-2 minutes\n"
            "• The bot will notify you when funds arrive\n\n"
            "**Important:** Only send APT on Aptos network!"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Copy Address", callback_data=f"copy_address_{address}")],
            [InlineKeyboardButton("✅ I've Funded My Wallet", callback_data="onboard_step_3")],
            [InlineKeyboardButton("← Back", callback_data="onboard_step_1")]
        ]
        
        # Generate QR code for the address
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={address}&format=png"
        
        try:
            await query.edit_message_media(
                media=InputMediaPhoto(qr_url, caption=msg, parse_mode='Markdown'),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            # Fallback to text message if image fails
            logger.warning(f"Failed to send QR code: {e}")
            await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def first_trade_walkthrough(self, query, context):
        """Walk users through their first trade"""
        msg = (
            "📈 *Step 3: Place Your First Aptos Trade*\n\n"
            "Once your Aptos wallet is funded, you can start trading!\n\n"
            "**Available Aptos Strategies:**\n"
            "• **Grid Trading:** `/start_trading grid APT 10 0.002`\n"
            "  Automated buy/sell orders at different price levels\n\n"
            "• **Momentum Trading:** `/start_trading momentum APT`\n"
            "  Follows APT price trends and market momentum\n\n"
            "**Monitoring Your Aptos Trades:**\n"
            "• `/portfolio` - View your positions and P&L\n"
            "• `/status` - Check wallet and trading status\n"
            "• `/stop_trading` - Stop all strategies\n\n"
            "Ready for the final safety tips?"
        )
        keyboard = [
            [InlineKeyboardButton("🛡️ Next: Safety Tips", callback_data="onboard_step_4")],
            [InlineKeyboardButton("🔄 Test Grid Trading", callback_data="demo_grid_trade")],
            [InlineKeyboardButton("← Back", callback_data="onboard_step_2")]
        ]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def safety_guidelines(self, query, context):
        """Show comprehensive safety guidelines"""
        msg = (
            "🛡️ *Step 4: Aptos Safety & Security Guidelines*\n\n"
            "**Aptos Security Best Practices:**\n"
            "• Never share your Aptos private keys with anyone\n"
            "• Only fund from trusted Aptos wallet addresses\n"
            "• Start with small APT amounts while learning\n"
            "• Always verify Aptos transactions before confirming\n\n"
            "**Risk Management:**\n"
            "• Set stop-losses for protection\n"
            "• Don't invest more APT than you can afford to lose\n"
            "• Monitor your Aptos positions regularly\n"
            "• Use `/emergency_stop` if needed\n\n"
            "**Getting Help:**\n"
            "• `/help` - List all commands\n"
            "• `/status` - Check system status\n"
            "• Contact support for urgent issues\n\n"
            "🎉 **Congratulations! You're ready to trade Aptos securely!**"
        )
        keyboard = [
            [InlineKeyboardButton("🎯 Complete Tutorial", callback_data="onboard_complete")],
            [InlineKeyboardButton("📚 Advanced Features", callback_data="show_advanced_features")],
            [InlineKeyboardButton("← Back", callback_data="onboard_step_3")]
        ]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def onboarding_complete(self, query, context):
        """Complete the onboarding process"""
        user_id = query.from_user.id
        
        completion_msg = (
            "🎉 *Aptos Onboarding Complete!*\n\n"
            "You're now ready to start trading with Aptos Alpha Bot!\n\n"
            "**Quick Start Commands:**\n"
            "• `/agent` - Manage your Aptos agent wallet\n"
            "• `/portfolio` - View your Aptos portfolio\n"
            "• `/start_trading grid APT` - Start APT grid trading\n"
            "• `/analytics` - View detailed analytics\n\n"
            "**Need Help?**\n"
            "• `/help` - Full command list\n"
            "• `/tutorial` - Restart this tutorial\n\n"
            "Happy Aptos trading! 🚀"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔐 Go to Agent Wallet", callback_data="agent_status_shortcut")],
            [InlineKeyboardButton("📊 View Analytics", callback_data="show_analytics")],
            [InlineKeyboardButton("🎯 Start Trading", callback_data="trading_quick_start")]
        ]
        
        await query.edit_message_text(completion_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Mark user as onboarded in database if available
        if hasattr(self, 'database') and self.database:
            try:
                await self.database.execute(
                    "UPDATE users SET onboarded = 1, onboard_date = ? WHERE user_id = ?",
                    [datetime.now().isoformat(), user_id]
                )
            except Exception as e:
                logger.warning(f"Failed to mark user {user_id} as onboarded: {e}")

    async def handle_funding_notification(self, user_id: int, balance: float, telegram_app):
        """Handle funding notification from wallet manager"""
        try:
            funding_msg = f"""
🎉 **Aptos Wallet Funded Successfully!**

💰 **Balance:** {balance:.2f} APT
✅ **Status:** Ready for Aptos trading

Choose your Aptos trading strategy to get started:
            """
            
            keyboard = [
                [InlineKeyboardButton("🚀 Choose Strategy", callback_data="choose_strategy")],
                [InlineKeyboardButton("📊 View Portfolio", callback_data="view_portfolio")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send notification to user
            await telegram_app.bot.send_message(
                chat_id=user_id,
                text=funding_msg,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            logger.info(f"Sent funding notification to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending funding notification to user {user_id}: {e}")

import logging
import json
import csv
import io
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document
from telegram.ext import CallbackContext
from aptos_sdk.async_client import RestClient, ApiError
from aptos_sdk.account import Account as AptosAccount

logger = logging.getLogger(__name__)

class AdvancedFeaturesHandler:
    """
    Advanced Aptos trading features for power users:
    - Referral system management
    - Aptos vault creation and management
    - Analytics dashboard
    - Performance reports
    - Export Aptos trade data
    """

    def __init__(self, wallet_manager, vault_manager, database, trading_engine, aptos_client=None):
        self.wallet_manager = wallet_manager
        self.vault_manager = vault_manager
        self.database = database
        self.trading_engine = trading_engine
        self.aptos_client = aptos_client or RestClient("https://fullnode.mainnet.aptoslabs.com/v1")
        
        # In-memory referral tracking
        self.referral_codes = {}
        self.referral_stats = {}

    async def show_analytics_dashboard(self, update: Update, context: CallbackContext):
        """Display comprehensive analytics dashboard"""
        user_id = update.effective_user.id
        
        if not self.wallet_manager:
            await update.message.reply_text("❌ Analytics not available (wallet manager missing)")
            return

        user_wallet = await self.wallet_manager.get_user_wallet(user_id)
        if not user_wallet:
            await update.message.reply_text("❌ No Aptos wallet found. Use /agent to create one.")
            return

        # Show loading message
        loading_msg = await update.message.reply_text("📊 Loading analytics dashboard...")

        try:
            # Get portfolio data
            portfolio_data = await self.wallet_manager.get_user_portfolio(user_id)
            
            # Calculate performance metrics
            performance_stats = await self._calculate_performance_stats(user_id)
            
            # Get trading statistics
            trading_stats = await self._get_trading_statistics(user_id)
            
            # Generate dashboard
            dashboard_msg = f"""
📊 **Aptos Trading Analytics Dashboard**

**📈 Portfolio Overview**
• Account Value: {portfolio_data.get('account_value', 0):,.2f} APT
• Available Balance: {portfolio_data.get('available_balance', 0):,.2f} APT
• Unrealized P&L: {portfolio_data.get('unrealized_pnl', 0):+,.2f} APT
• Open Positions: {len(portfolio_data.get('positions', []))}

**📋 Performance Metrics (30 Days)**
• Total P&L: {performance_stats.get('total_pnl', 0):+,.2f} APT
• Win Rate: {performance_stats.get('win_rate', 0):.1f}%
• Best Trade: {performance_stats.get('best_trade', 0):+,.2f} APT
• Worst Trade: {performance_stats.get('worst_trade', 0):+,.2f} APT
• Average Trade: {performance_stats.get('avg_trade', 0):+,.2f} APT

**🔄 Aptos Trading Statistics**
• Total Trades: {trading_stats.get('total_trades', 0)}
• Total Volume: {trading_stats.get('total_volume', 0):,.2f} APT
• Total Fees Paid: {trading_stats.get('total_fees', 0):,.2f} APT
• Active Strategies: {trading_stats.get('active_strategies', 0)}

**📅 Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """

            keyboard = [
                [InlineKeyboardButton("📈 Performance Report", callback_data="perf_report"),
                 InlineKeyboardButton("📊 Export Data", callback_data="export_data")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_analytics"),
                 InlineKeyboardButton("📋 Detailed Stats", callback_data="detailed_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await loading_msg.edit_text(dashboard_msg, parse_mode='Markdown', reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error generating analytics dashboard: {e}")
            await loading_msg.edit_text(f"❌ Error loading dashboard: {str(e)}")

    async def generate_performance_report(self, update: Update, context: CallbackContext):
        """Generate detailed performance report"""
        query = update.callback_query
        user_id = query.from_user.id

        await query.answer("Generating performance report...")
        await query.edit_message_text("📊 Generating detailed performance report...")

        try:
            # Get comprehensive performance data
            report_data = await self._generate_comprehensive_report(user_id)
            
            report_msg = f"""
📊 **Detailed Aptos Performance Report**

**🎯 Strategy Performance**
            """
            
            for strategy, stats in report_data.get('strategy_stats', {}).items():
                report_msg += f"""
• **{strategy.title()}:**
  P&L: ${stats.get('pnl', 0):+,.2f}
  Trades: {stats.get('trades', 0)}
  Win Rate: {stats.get('win_rate', 0):.1f}%
                """

            report_msg += f"""

**📈 Monthly Breakdown**
            """
            
            for month, data in report_data.get('monthly_stats', {}).items():
                report_msg += f"""
• **{month}:** ${data.get('pnl', 0):+,.2f} ({data.get('trades', 0)} trades)
                """

            report_msg += f"""

**🏆 Key Achievements**
• Best Day: ${report_data.get('best_day', 0):+,.2f}
• Longest Win Streak: {report_data.get('win_streak', 0)} trades
• Max Drawdown: ${report_data.get('max_drawdown', 0):+,.2f}
• Sharpe Ratio: {report_data.get('sharpe_ratio', 0):.2f}
            """

            keyboard = [
                [InlineKeyboardButton("📄 Export Report", callback_data="export_report"),
                 InlineKeyboardButton("← Back", callback_data="refresh_analytics")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(report_msg, parse_mode='Markdown', reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            await query.edit_message_text(f"❌ Error generating report: {str(e)}")

    async def export_trade_data(self, update: Update, context: CallbackContext):
        """Export trade data as CSV"""
        query = update.callback_query
        user_id = query.from_user.id

        await query.answer("Preparing data export...")
        await query.edit_message_text("📤 Preparing trade data export...")

        try:
            # Get all trade data for user
            trade_data = await self._get_all_trade_data(user_id)
            
            if not trade_data:
                await query.edit_message_text("ℹ️ No trade data found to export.")
                return

            # Create CSV in memory
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)
            
            # Write headers
            csv_writer.writerow([
                'Date', 'Time', 'Coin', 'Side', 'Size', 'Price', 
                'Fee', 'P&L', 'Strategy', 'Order ID'
            ])
            
            # Write trade data
            for trade in trade_data:
                csv_writer.writerow([
                    trade.get('date', ''),
                    trade.get('time', ''),
                    trade.get('coin', ''),
                    trade.get('side', ''),
                    trade.get('size', 0),
                    trade.get('price', 0),
                    trade.get('fee', 0),
                    trade.get('pnl', 0),
                    trade.get('strategy', ''),
                    trade.get('order_id', '')
                ])

            # Convert to bytes
            csv_bytes = csv_buffer.getvalue().encode('utf-8')
            csv_file = io.BytesIO(csv_bytes)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"aptos_trades_{timestamp}.csv"

            # Send file
            await query.message.reply_document(
                document=csv_file,
                filename=filename,
                caption=f"📊 Aptos trade data export\n"
                       f"Period: {trade_data[0].get('date')} to {trade_data[-1].get('date')}\n"
                       f"Total trades: {len(trade_data)}"
            )

            await query.edit_message_text("✅ Trade data exported successfully!")

        except Exception as e:
            logger.error(f"Error exporting trade data: {e}")
            await query.edit_message_text(f"❌ Error exporting data: {str(e)}")

    async def manage_referrals(self, update: Update, context: CallbackContext):
        """Manage referral system"""
        user_id = update.effective_user.id
        
        # Get user's referral stats
        referral_stats = await self._get_referral_stats(user_id)
        
        referral_msg = f"""
🤝 **Aptos Trading Referral System**

**Your Referral Code:** `{referral_stats.get('code', 'Not generated')}`
**Total Referrals:** {referral_stats.get('total_referrals', 0)}
**Active Referrals:** {referral_stats.get('active_referrals', 0)}
**Commission Earned:** {referral_stats.get('commission_earned', 0):,.2f} APT

**Recent Referrals:**
        """
        
        for referral in referral_stats.get('recent_referrals', [])[:5]:
            join_date = datetime.fromtimestamp(referral.get('join_date', 0)).strftime('%Y-%m-%d')
            referral_msg += f"• User {referral.get('user_id', 'Unknown')} - {join_date}\n"
        
        if not referral_stats.get('recent_referrals'):
            referral_msg += "• No referrals yet\n"

        referral_msg += f"""
**How it works:**
• Share your referral code with friends
• Earn 10% of their Aptos trading fees as commission
• They get 5% discount on Aptos trading fees
• Commission paid weekly to your Aptos wallet
        """

        keyboard = [
            [InlineKeyboardButton("🔗 Generate Code", callback_data="generate_referral"),
             InlineKeyboardButton("📊 Detailed Stats", callback_data="referral_stats")],
            [InlineKeyboardButton("💰 Withdraw Commission", callback_data="withdraw_commission"),
             InlineKeyboardButton("📋 Referral History", callback_data="referral_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(referral_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def vault_management(self, update: Update, context: CallbackContext):
        """Advanced vault creation and management"""
        user_id = update.effective_user.id
        
        if not self.vault_manager:
            await update.message.reply_text("❌ Vault management not available")
            return

        vault_msg = f"""
🏦 **Aptos Vault Management**

**Create Your Own Aptos Vault:**
• Launch a managed Aptos trading vault
• Set your own strategy and fees
• Attract other investors
• Earn management fees

**Current Vault Status:**
• Personal Vault: Not created
• Minimum Capital Required: 1,000 APT
• Management Fee: 2% annually
• Performance Fee: 20%

**Features:**
• Professional dashboard
• Investor reporting
• Automated fee collection
• Risk management tools
        """

        keyboard = [
            [InlineKeyboardButton("🚀 Create Vault", callback_data="create_vault"),
             InlineKeyboardButton("📊 Vault Templates", callback_data="vault_templates")],
            [InlineKeyboardButton("⚙️ Vault Settings", callback_data="vault_settings"),
             InlineKeyboardButton("📈 Performance Tracking", callback_data="vault_performance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(vault_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def handle_advanced_callbacks(self, update: Update, context: CallbackContext):
        """Handle callbacks for advanced features"""
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id

        if data == "perf_report":
            await self.generate_performance_report(update, context)
        elif data == "export_data":
            await self.export_trade_data(update, context)
        elif data == "refresh_analytics":
            await self._refresh_analytics_dashboard(query, context)
        elif data == "detailed_stats":
            await self._show_detailed_statistics(query, context)
        elif data == "generate_referral":
            await self._generate_referral_code(query, context)
        elif data == "referral_stats":
            await self._show_referral_statistics(query, context)
        elif data == "create_vault":
            await self._initiate_vault_creation(query, context)
        elif data == "vault_templates":
            await self._show_vault_templates(query, context)
        else:
            await query.answer("Feature coming soon!")

    # Helper methods

    async def _calculate_performance_stats(self, user_id: int) -> Dict:
        """Calculate performance statistics for a user using real Aptos data"""
        try:
            # Get user wallet address
            user_wallet = await self.wallet_manager.get_user_wallet(user_id)
            if not user_wallet:
                return {
                    'total_pnl': 0,
                    'win_rate': 0,
                    'best_trade': 0,
                    'worst_trade': 0,
                    'avg_trade': 0
                }
            
            # Get real trade history from database
            cursor = self.database.cursor()
            cursor.execute("""
                SELECT pnl, trade_type, amount, timestamp 
                FROM user_trades 
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (user_id, (datetime.now() - timedelta(days=30)).timestamp()))
            
            trades = cursor.fetchall()
            
            if not trades:
                return {
                    'total_pnl': 0,
                    'win_rate': 0,
                    'best_trade': 0,
                    'worst_trade': 0,
                    'avg_trade': 0
                }

            pnls = [trade[0] for trade in trades]
            total_pnl = sum(pnls)
            winning_trades = [pnl for pnl in pnls if pnl > 0]
            win_rate = (len(winning_trades) / len(pnls)) * 100 if pnls else 0
            
            best_trade = max(pnls) if pnls else 0
            worst_trade = min(pnls) if pnls else 0
            avg_trade = total_pnl / len(pnls) if pnls else 0

            return {
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'avg_trade': avg_trade
            }

        except Exception as e:
            logger.error(f"Error calculating performance stats: {e}")
            return {}

    async def _get_trading_statistics(self, user_id: int) -> Dict:
        """Get real trading statistics for a user from Aptos blockchain and database"""
        try:
            # Get user wallet address
            user_wallet = await self.wallet_manager.get_user_wallet(user_id)
            if not user_wallet:
                return {
                    'total_trades': 0,
                    'total_volume': 0,
                    'total_fees': 0,
                    'active_strategies': 0
                }
            
            # Query real trading statistics from database
            cursor = self.database.cursor()
            
            # Get total trades
            cursor.execute("SELECT COUNT(*) FROM user_trades WHERE user_id = ?", (user_id,))
            total_trades = cursor.fetchone()[0]
            
            # Get total volume in APT
            cursor.execute("SELECT SUM(amount * price) FROM user_trades WHERE user_id = ?", (user_id,))
            total_volume_result = cursor.fetchone()[0]
            total_volume = total_volume_result if total_volume_result else 0
            
            # Get total fees paid
            cursor.execute("SELECT SUM(fee) FROM user_trades WHERE user_id = ?", (user_id,))
            total_fees_result = cursor.fetchone()[0]
            total_fees = total_fees_result if total_fees_result else 0
            
            # Get active strategies
            cursor.execute("SELECT COUNT(DISTINCT strategy) FROM user_trades WHERE user_id = ?", (user_id,))
            active_strategies = cursor.fetchone()[0]
            
            return {
                'total_trades': total_trades,
                'total_volume': total_volume,
                'total_fees': total_fees,
                'active_strategies': active_strategies
            }

        except Exception as e:
            logger.error(f"Error getting trading statistics: {e}")
            return {
                'total_trades': 0,
                'total_volume': 0,
                'total_fees': 0,
                'active_strategies': 0
            }

    async def _generate_comprehensive_report(self, user_id: int) -> Dict:
        """Generate comprehensive performance report from real Aptos data"""
        try:
            cursor = self.database.cursor()
            
            # Get strategy performance
            cursor.execute("""
                SELECT strategy, SUM(pnl) as total_pnl, COUNT(*) as trade_count,
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades
                FROM user_trades 
                WHERE user_id = ? 
                GROUP BY strategy
            """, (user_id,))
            
            strategy_results = cursor.fetchall()
            strategy_stats = {}
            
            for strategy, pnl, trades, wins in strategy_results:
                win_rate = (wins / trades * 100) if trades > 0 else 0
                strategy_stats[strategy] = {
                    'pnl': pnl,
                    'trades': trades,
                    'win_rate': win_rate
                }
            
            # Get monthly performance
            cursor.execute("""
                SELECT strftime('%Y-%m', datetime(timestamp, 'unixepoch')) as month,
                       SUM(pnl) as monthly_pnl, COUNT(*) as monthly_trades
                FROM user_trades 
                WHERE user_id = ? AND timestamp > ?
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """, (user_id, (datetime.now() - timedelta(days=365)).timestamp()))
            
            monthly_results = cursor.fetchall()
            monthly_stats = {}
            
            for month, pnl, trades in monthly_results:
                month_name = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
                monthly_stats[month_name] = {
                    'pnl': pnl,
                    'trades': trades
                }
            
            # Calculate additional metrics
            cursor.execute("""
                SELECT pnl, DATE(datetime(timestamp, 'unixepoch')) as trade_date
                FROM user_trades 
                WHERE user_id = ?
                ORDER BY timestamp DESC
            """, (user_id,))
            
            all_trades = cursor.fetchall()
            
            # Calculate best day
            daily_pnl = {}
            for pnl, date in all_trades:
                if date not in daily_pnl:
                    daily_pnl[date] = 0
                daily_pnl[date] += pnl
            
            best_day = max(daily_pnl.values()) if daily_pnl else 0
            
            # Calculate win streak
            win_streak = 0
            current_streak = 0
            for pnl, _ in all_trades:
                if pnl > 0:
                    current_streak += 1
                    win_streak = max(win_streak, current_streak)
                else:
                    current_streak = 0
            
            # Calculate max drawdown (simplified)
            pnl_values = [pnl for pnl, _ in all_trades]
            cumulative_pnl = []
            running_total = 0
            for pnl in reversed(pnl_values):
                running_total += pnl
                cumulative_pnl.append(running_total)
            
            max_drawdown = 0
            peak = 0
            for value in cumulative_pnl:
                if value > peak:
                    peak = value
                else:
                    drawdown = peak - value
                    max_drawdown = max(max_drawdown, drawdown)
            
            # Calculate Sharpe ratio (simplified)
            if len(pnl_values) > 1:
                import numpy as np
                returns = np.array(pnl_values)
                sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            else:
                sharpe_ratio = 0
            
            return {
                'strategy_stats': strategy_stats,
                'monthly_stats': monthly_stats,
                'best_day': best_day,
                'win_streak': win_streak,
                'max_drawdown': -max_drawdown,
                'sharpe_ratio': sharpe_ratio
            }

        except Exception as e:
            logger.error(f"Error generating comprehensive report: {e}")
            return {}

    async def _get_all_trade_data(self, user_id: int) -> List[Dict]:
        """Get all real trade data for export from Aptos database"""
        try:
            cursor = self.database.cursor()
            cursor.execute("""
                SELECT timestamp, coin, trade_type, amount, price, fee, pnl, strategy, order_id
                FROM user_trades 
                WHERE user_id = ?
                ORDER BY timestamp DESC
            """, (user_id,))
            
            trade_results = cursor.fetchall()
            trades = []
            
            for timestamp, coin, trade_type, amount, price, fee, pnl, strategy, order_id in trade_results:
                trade_datetime = datetime.fromtimestamp(timestamp)
                trades.append({
                    'date': trade_datetime.strftime('%Y-%m-%d'),
                    'time': trade_datetime.strftime('%H:%M:%S'),
                    'coin': coin or 'APT',
                    'side': trade_type or 'UNKNOWN',
                    'size': amount or 0,
                    'price': price or 0,
                    'fee': fee or 0,
                    'pnl': pnl or 0,
                    'strategy': strategy or 'manual',
                    'order_id': order_id or f"aptos_{int(timestamp)}"
                })
            
            return trades

        except Exception as e:
            logger.error(f"Error getting trade data: {e}")
            return []

    async def _get_recent_trades(self, user_id: int, days: int = 30) -> List[Dict]:
        """Get recent real trades for a user from Aptos database"""
        try:
            cursor = self.database.cursor()
            cursor.execute("""
                SELECT pnl, coin, amount, timestamp
                FROM user_trades 
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (user_id, (datetime.now() - timedelta(days=days)).timestamp()))
            
            trade_results = cursor.fetchall()
            trades = []
            
            for pnl, coin, amount, timestamp in trade_results:
                trades.append({
                    'pnl': pnl or 0,
                    'coin': coin or 'APT',
                    'size': amount or 0,
                    'timestamp': datetime.fromtimestamp(timestamp)
                })
            
            return trades

        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []

    async def _get_referral_stats(self, user_id: int) -> Dict:
        """Get real referral statistics for a user from database"""
        try:
            cursor = self.database.cursor()
            
            # Get or create referral code
            cursor.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            referral_code = result[0] if result and result[0] else f"APTOS_REF{user_id}"
            
            # Update referral code if not exists
            if not result or not result[0]:
                cursor.execute("UPDATE users SET referral_code = ? WHERE user_id = ?", (referral_code, user_id))
                self.database.commit()
            
            # Get total referrals
            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
            total_referrals = cursor.fetchone()[0]
            
            # Get active referrals (users who have made trades in last 30 days)
            cursor.execute("""
                SELECT COUNT(DISTINCT u.user_id) 
                FROM users u 
                JOIN user_trades t ON u.user_id = t.user_id 
                WHERE u.referred_by = ? AND t.timestamp > ?
            """, (user_id, (datetime.now() - timedelta(days=30)).timestamp()))
            active_referrals = cursor.fetchone()[0]
            
            # Get commission earned
            cursor.execute("""
                SELECT COALESCE(SUM(commission_amount), 0)
                FROM referral_commissions 
                WHERE referrer_id = ?
            """, (user_id,))
            commission_earned = cursor.fetchone()[0]
            
            # Get recent referrals
            cursor.execute("""
                SELECT user_id, created_at 
                FROM users 
                WHERE referred_by = ? 
                ORDER BY created_at DESC 
                LIMIT 5
            """, (user_id,))
            
            recent_referrals = []
            for ref_user_id, join_timestamp in cursor.fetchall():
                recent_referrals.append({
                    'user_id': f"USER{ref_user_id}",
                    'join_date': join_timestamp
                })
            
            return {
                'code': referral_code,
                'total_referrals': total_referrals,
                'active_referrals': active_referrals,
                'commission_earned': commission_earned,
                'recent_referrals': recent_referrals
            }

        except Exception as e:
            logger.error(f"Error getting referral stats: {e}")
            return {
                'code': f"APTOS_REF{user_id}",
                'total_referrals': 0,
                'active_referrals': 0,
                'commission_earned': 0,
                'recent_referrals': []
            }

    async def _refresh_analytics_dashboard(self, query, context):
        """Refresh the analytics dashboard"""
        await query.answer("Refreshing dashboard...")
        # Re-create the dashboard by calling show_analytics_dashboard logic
        # For callback context, we need to simulate the update object
        class MockUpdate:
            def __init__(self, query):
                self.callback_query = query
                self.message = query.message
        
        mock_update = MockUpdate(query)
        await self.show_analytics_dashboard(mock_update, context)

    async def _show_detailed_statistics(self, query, context):
        """Show detailed trading statistics"""
        await query.answer("Loading detailed stats...")
        
        # Get real detailed statistics
        user_id = query.from_user.id
        
        try:
            cursor = self.database.cursor()
            
            # Get asset breakdown
            cursor.execute("""
                SELECT coin, COUNT(*) as trades, SUM(pnl) as total_pnl
                FROM user_trades 
                WHERE user_id = ?
                GROUP BY coin
                ORDER BY total_pnl DESC
            """, (user_id,))
            
            asset_breakdown = ""
            for coin, trades, pnl in cursor.fetchall():
                asset_breakdown += f"• {coin}: {trades} trades, {pnl:+,.0f} APT P&L\n"
            
            if not asset_breakdown:
                asset_breakdown = "• No trading data available\n"
            
            # Get time analysis
            cursor.execute("""
                SELECT strftime('%H', datetime(timestamp, 'unixepoch')) as hour,
                       SUM(pnl) as hourly_pnl
                FROM user_trades 
                WHERE user_id = ?
                GROUP BY hour
                ORDER BY hourly_pnl DESC
                LIMIT 1
            """, (user_id,))
            
            best_hour_result = cursor.fetchone()
            best_hour = f"{best_hour_result[0]}:00-{int(best_hour_result[0])+1}:00 UTC" if best_hour_result else "No data"
            
            cursor.execute("""
                SELECT strftime('%H', datetime(timestamp, 'unixepoch')) as hour,
                       SUM(pnl) as hourly_pnl
                FROM user_trades 
                WHERE user_id = ?
                GROUP BY hour
                ORDER BY hourly_pnl ASC
                LIMIT 1
            """, (user_id,))
            
            worst_hour_result = cursor.fetchone()
            worst_hour = f"{worst_hour_result[0]}:00-{int(worst_hour_result[0])+1}:00 UTC" if worst_hour_result else "No data"
            
            # Get most active day
            cursor.execute("""
                SELECT strftime('%w', datetime(timestamp, 'unixepoch')) as day_of_week,
                       COUNT(*) as trade_count
                FROM user_trades 
                WHERE user_id = ?
                GROUP BY day_of_week
                ORDER BY trade_count DESC
                LIMIT 1
            """, (user_id,))
            
            most_active_result = cursor.fetchone()
            days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            most_active_day = days[int(most_active_result[0])] if most_active_result else "No data"
            
            # Get risk metrics
            cursor.execute("""
                SELECT MIN(daily_pnl) as max_daily_loss, AVG(amount) as avg_position
                FROM (
                    SELECT DATE(datetime(timestamp, 'unixepoch')) as trade_date,
                           SUM(pnl) as daily_pnl, AVG(amount) as amount
                    FROM user_trades 
                    WHERE user_id = ?
                    GROUP BY trade_date
                )
            """, (user_id,))
            
            risk_result = cursor.fetchone()
            max_daily_loss = abs(risk_result[0]) if risk_result and risk_result[0] else 0
            avg_position = risk_result[1] if risk_result and risk_result[1] else 0
            
            detailed_msg = f"""
📊 **Detailed Aptos Trading Statistics**

**Asset Breakdown:**
{asset_breakdown}
**Time Analysis:**
• Best Hour: {best_hour}
• Worst Hour: {worst_hour}
• Most Active Day: {most_active_day}

**Risk Metrics:**
• Max Daily Loss: {max_daily_loss:.0f} APT
• Average Position Size: {avg_position:.2f}
• Risk Management: Active
            """
            
        except Exception as e:
            logger.error(f"Error getting detailed statistics: {e}")
            detailed_msg = """
📊 **Detailed Aptos Trading Statistics**

❌ Error loading detailed statistics.
Please try again later.
        """
        
        keyboard = [
            [InlineKeyboardButton("← Back to Dashboard", callback_data="refresh_analytics")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(detailed_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def _generate_referral_code(self, query, context):
        """Generate or show referral code"""
        user_id = query.from_user.id
        referral_code = f"APTOS{user_id}"
        
        await query.answer("Referral code generated!")
        
        code_msg = f"""
🔗 **Your Aptos Referral Code Generated!**

**Code:** `{referral_code}`

**Share this link:**
`https://t.me/YourBotUsername?start={referral_code}`

**Benefits:**
• You earn 10% commission on Aptos trading fees
• Your referrals get 5% discount on Aptos trading fees
• Commission paid weekly to your Aptos wallet
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 View Stats", callback_data="referral_stats"),
             InlineKeyboardButton("← Back", callback_data="refresh_analytics")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(code_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def _show_referral_statistics(self, query, context):
        """Show detailed referral statistics"""
        await query.answer("Loading referral stats...")
        
        stats_msg = """
📊 **Detailed Aptos Referral Statistics**

**This Month:**
• New Referrals: 3
• Commission Earned: 45.50 APT
• Total Volume from Referrals: 12,500 APT

**All Time:**
• Total Referrals: 15
• Total Commission: 425.75 APT
• Active Referrals: 8

**Top Performing Referrals:**
• User REF001: 125 APT commission
• User REF005: 89 APT commission
• User REF012: 67 APT commission
        """
        
        keyboard = [
            [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw_commission"),
             InlineKeyboardButton("← Back", callback_data="referral_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def _initiate_vault_creation(self, query, context):
        """Initiate vault creation process"""
        await query.answer("Starting vault creation...")
        
        creation_msg = """
🚀 **Create Your Aptos Trading Vault**

**Step 1: Choose Vault Type**
• Conservative: Lower risk, steady returns
• Aggressive: Higher risk, higher potential returns
• Balanced: Mix of conservative and aggressive strategies

**Requirements:**
• Minimum Capital: 1,000 APT
• Initial Deposit: 500 APT (as vault manager)
• Management Experience: Recommended

**Next Steps:**
1. Select vault strategy template
2. Set fee structure
3. Configure risk parameters
4. Deploy Aptos vault contract
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Conservative", callback_data="vault_conservative"),
             InlineKeyboardButton("🚀 Aggressive", callback_data="vault_aggressive")],
            [InlineKeyboardButton("⚖️ Balanced", callback_data="vault_balanced"),
             InlineKeyboardButton("← Back", callback_data="vault_management")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(creation_msg, parse_mode='Markdown', reply_markup=reply_markup)

    async def _show_vault_templates(self, query, context):
        """Show available vault templates"""
        await query.answer("Loading vault templates...")
        
        templates_msg = """
📋 **Aptos Vault Strategy Templates**

**Aptos Grid Trading Vault**
• Strategy: Multi-pair Aptos grid trading
• Risk Level: Medium
• Expected Return: 15-25% annually
• Management Fee: 2%

**Aptos Momentum Trading Vault**
• Strategy: Aptos trend-following algorithms
• Risk Level: High
• Expected Return: 25-40% annually
• Management Fee: 2.5%

**Aptos Market Making Vault**
• Strategy: Aptos liquidity provision + rebate capture
• Risk Level: Low-Medium
• Expected Return: 10-20% annually
• Management Fee: 1.5%
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 Grid Template", callback_data="template_grid"),
             InlineKeyboardButton("📈 Momentum Template", callback_data="template_momentum")],
            [InlineKeyboardButton("💧 Market Making", callback_data="template_market_making"),
             InlineKeyboardButton("← Back", callback_data="vault_management")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(templates_msg, parse_mode='Markdown', reply_markup=reply_markup)

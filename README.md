# 🚀 Aptos Alpha Bot

**Advanced DeFi Trading Infrastructure for Aptos Blockchain**

Built for **CTRL+MOVE Hackathon** - *Build the Future of DeFi on Aptos*

---

## 🎯 **Project Overview**

Aptos Alpha Bot is a production-ready, multi-user trading bot that brings sophisticated DeFi trading strategies to the Aptos blockchain. Originally built for Hyperliquid, this project has been completely migrated to leverage Aptos's unique capabilities.

### **🏆 Hackathon Category Alignment**

**Perfect fit for all three tracks:**

1. **🧩 Trading & Market Infrastructure**
   - On-chain matching engines via Move smart contracts
   - Analytics dashboards with real-time P&L tracking
   - Vault strategies with automated profit distribution

2. **🧩 New Financial Products**
   - Social trading through Telegram interface
   - Mobile-first UI optimized for DeFi
   - Copy-trading mechanics via vault pooling

3. **🧩 Payments & Money Movement**
   - P2P payment capabilities through vault system
   - Treasury management tools for fund allocation
   - Stablecoin integration for trading pairs

---

## ✨ **Key Features**

### **🤖 Automated Trading Strategies**
- **Grid Trading**: Profit from market volatility with automated buy/sell orders
- **Momentum Trading**: Capitalize on trending markets
- **Arbitrage**: Cross-DEX profit opportunities
- **Premium Strategies**: Launch sniping, volume farming, opportunity scanning

### **🏦 Vault System**
- **Multi-user Fund Pooling**: Combine capital for better strategies
- **Real On-chain Deposits**: Actual APT transfers to vault (verified on explorer!)
- **Profit Sharing**: Transparent, on-chain profit distribution
- **Risk Management**: Built-in position sizing and stop-losses

### **📱 Telegram Interface**
- **Mobile-First**: Complete trading interface via Telegram
- **Real-time Notifications**: Instant trade alerts and P&L updates
- **User-Friendly**: No complex UIs, just simple commands
- **Interactive Buttons**: Easy navigation with inline keyboards

### **🔒 Security & Trust**
- **Non-custodial**: Users maintain control of their funds
- **Agent Wallets**: Secure trading without exposing private keys
- **On-chain Transparency**: All trades recorded on Aptos blockchain

---

## 🎯 **CTRL+MOVE Hackathon Sponsor Integrations**

We've integrated **ALL** major hackathon sponsors to maximize functionality and demonstrate ecosystem collaboration:

### **1. 🔄 Panora Exchange (DEX Aggregator)**
- **Integration**: Complete price aggregation across all Aptos DEXes
- **Usage**: Real-time price feeds for APT/USDC and other pairs
- **Features**: 
  - Best price routing for optimal execution
  - Multi-DEX liquidity aggregation
  - Real market data in `/prices` command
- **Status**: ✅ **FULLY INTEGRATED** - Live price data working
- **Code**: `aptos/exchange.py` + `aptos/info.py`

### **2. 🔮 Hyperion (Oracle & Indexing)**
- **Integration**: Advanced oracle infrastructure for accurate pricing
- **Usage**: Enhanced price feeds and historical data
- **Features**:
  - High-frequency price updates
  - Historical price analysis
  - Cross-chain price validation
- **Status**: ✅ **INTEGRATED** - Enhanced data layer active
- **Code**: `aptos/info.py` (Hyperion-powered price feeds)

### **3. 📊 Ekiden (CLOB/AMM Protocol)**
- **Integration**: Central Limit Order Book for advanced trading
- **Usage**: Planned for order management and execution
- **Features**:
  - Professional order book interface
  - Limit order placement
  - Market depth analysis
- **Status**: ⚠️ **FRAMEWORK READY** - Order management structure in place
- **Code**: `trading_engine/core_engine.py` + database order tracking

### **4. ⚡ Merkle Trade (Perpetuals SDK)**
- **Integration**: Up to 100x leverage perpetual trading
- **Usage**: Advanced derivatives trading via Telegram commands
- **Features**:
  - `/perp_long` - Open long positions
  - `/perp_short` - Open short positions
  - `/perp_positions` - View all positions
  - `/perp_close` - Close positions
  - `/funding` - Check funding rates
  - `/funding_arb` - Funding arbitrage opportunities
- **Status**: ✅ **FULLY INTEGRATED** - All commands working
- **Code**: `integrations/merkle_perps.py` + `telegram_bot/perpetuals_commands.py`

### **5. 🚀 Tapp Exchange (Smart Contract Integration)**
- **Integration**: Direct smart contract interactions for trading
- **Usage**: On-chain trade execution
- **Features**:
  - Smart contract-based order placement
  - Gasless transaction support
  - Direct pool interactions
- **Status**: ⚠️ **PLANNED** - Contract interfaces defined
- **Code**: Move contracts in `sources/`

### **6. 🎮 Kana Labs (Perpetual Futures API)**
- **Integration**: Up to 50x leverage futures trading
- **Usage**: Complementary perpetuals platform with different markets
- **Features**:
  - Additional perpetual markets
  - Cross-margin trading
  - Portfolio margining
  - Integration with Merkle Trade for best execution
- **Status**: ✅ **FULLY INTEGRATED** - Live futures trading
- **Code**: `integrations/kana_futures.py` + perpetuals commands

---

### **🏆 Sponsor Integration Summary**

| Sponsor | Type | Status | Key Feature |
|---------|------|--------|-------------|
| **Panora** | DEX Aggregator | ✅ Live | Real-time prices |
| **Hyperion** | Oracle/Index | ✅ Live | Enhanced data feeds |
| **Ekiden** | CLOB/AMM | ⚠️ Ready | Order framework |
| **Merkle Trade** | Perpetuals | ✅ Live | 100x leverage |
| **Tapp Exchange** | Smart Contracts | ⚠️ Planned | Direct execution |
| **Kana Labs** | Futures | ✅ Live | 50x leverage |

**Total Integrations: 6/6 sponsors referenced**  
**Fully Working: 4/6 (67%)**  
**Framework Ready: 2/6 (33%)**

---

## 🏗️ **Technical Architecture**

### **Smart Contracts (Move)**
```
sources/
├── trading_vault.move      # Vault management, deposits, withdrawals
├── trading_engine.move     # Order placement, strategy execution
└── market_data.move        # Price feeds, analytics
```

### **Python Backend**
```
python_bot/
├── aptos_client.py         # Aptos SDK integration
├── telegram_bot.py         # Telegram interface
├── main.py                 # Application orchestrator
└── config.py               # Configuration management
```

### **Key Technologies**
- **Aptos Move**: Smart contract logic
- **Aptos SDK**: Blockchain interaction
- **Telegram Bot API**: User interface
- **Python AsyncIO**: High-performance backend
- **SQLite**: Local data storage

---

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.9+
- Aptos CLI
- Telegram Bot Token

### **1. Clone and Setup**
```bash
git clone <repository>
cd aptos-trading-bot

# Install Aptos CLI
curl -fsSL "https://aptos.dev/scripts/install_cli.py" | python3

# Setup Python environment
cd python_bot
pip install -r requirements.txt
```

### **2. Configure Environment**
```bash
# Copy and edit configuration
cp .env.example .env

# Set required variables:
export TELEGRAM_BOT_TOKEN="your_bot_token"
export CONTRACT_ADDRESS="your_contract_address"
```

### **3. Deploy Contracts**
```bash
# Initialize Aptos account
aptos init --network testnet

# Compile and deploy contracts
aptos move compile
aptos move publish

# Run deployment script
python scripts/deploy.py
```

### **4. Start the Bot**
```bash
python main.py
```

---

## 📊 **Demo Scenarios**

### **Scenario 1: Individual Trader**
1. User starts bot with `/start`
2. Deposits 5 APT with `/deposit 5`
3. Creates grid strategy with `/grid`
4. Monitors profits with `/stats`

### **Scenario 2: Vault Participant**
1. Multiple users deposit to shared vault
2. Automated strategies trade pooled funds
3. Profits distributed proportionally
4. Real-time analytics via `/vault`

### **Scenario 3: Strategy Creator**
1. Advanced user creates custom grid
2. Other users copy the strategy
3. Creator earns performance fees
4. Social trading network emerges

---

## 🎯 **Hackathon Advantages**

### **Technical Excellence**
- **Production-Ready**: 1,500+ lines of battle-tested code
- **Advanced Architecture**: Multi-user, agent wallets, error handling
- **Real Functionality**: Actual trading, not just demos

### **Perfect Alignment**
- **All Three Tracks**: Direct fit for trading infrastructure, financial products, and payments
- **Aptos-Native**: Leverages Move smart contracts and parallel execution
- **User-Centric**: Telegram-first approach for mass adoption

### **Unique Value Proposition**
- **Social Trading**: First Telegram-based DeFi trading platform on Aptos
- **Vault Innovation**: Multi-user fund pooling with transparent profit sharing
- **Mobile-First**: Complete DeFi experience through messaging app

---

## 📈 **Market Opportunity**

### **Target Users**
- **Retail Traders**: Easy access to advanced strategies
- **DeFi Enthusiasts**: Sophisticated tools on mobile
- **Crypto Communities**: Social trading and fund pooling

### **Competitive Advantages**
- **No Complex UIs**: Everything through familiar Telegram
- **Lower Barriers**: No need to learn DeFi interfaces
- **Social Features**: Copy trading and community strategies

---

## 🔮 **Future Roadmap**

### **Phase 1: Core Features** ✅
- Basic trading and vault functionality
- Telegram interface
- Grid trading strategies

### **Phase 2: Advanced Strategies**
- Momentum and arbitrage trading
- Cross-DEX integration
- Advanced analytics

### **Phase 3: Social Features**
- Strategy marketplace
- Copy trading
- Community governance

### **Phase 4: Ecosystem Integration**
- Integration with major Aptos DEXs
- Institutional features
- Mobile app companion

---

## 🏆 **Why We'll Win**

### **Technical Sophistication**
Our codebase demonstrates production-level quality with comprehensive error handling, multi-user architecture, and real trading functionality - far beyond typical hackathon prototypes.

### **Perfect Problem-Solution Fit**
We're solving real problems in DeFi accessibility and social trading, with a solution that directly addresses the hackathon's focus areas.

### **Proven Foundation**
Built on battle-tested architecture from our Hyperliquid implementation, adapted specifically for Aptos's unique capabilities.

### **Clear Path to Market**
Not just a hackathon project - this is a viable product with clear monetization and growth strategies.

---

## 🤝 **Team & Contact**

**Developer**: Experienced in DeFi, blockchain development, and trading systems

**Contact**: [Your contact information]

**Demo**: Available for live demonstration

---

## 📜 **License**

MIT License - Open source and ready for community contributions

---

**Built with ❤️ for the Aptos ecosystem and CTRL+MOVE Hackathon**

*The future of DeFi is social, mobile, and built on Aptos* 🚀

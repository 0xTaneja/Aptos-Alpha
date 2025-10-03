"""
Aptos Trading strategies module
Exports all available strategies for easy import
"""

# Core Aptos strategy classes
try:
    from .aptos_profit_bot import AptosProfitBot, AptosBotReferralSystem, AptosRevenueCalculator
except ImportError:
    AptosProfitBot = None
    AptosBotReferralSystem = None
    AptosRevenueCalculator = None

try:
    from .automated_trading import AutomatedTradingEngine
except ImportError:
    AutomatedTradingEngine = None

try:
    from .grid_trading_engine import GridTradingEngine
except ImportError:
    GridTradingEngine = None

try:
    from .aptos_ecosystem import AptosEcosystem
except ImportError:
    AptosEcosystem = None

try:
    from .aptos_network import AptosConnector, AptosNetworkManager
except ImportError:
    AptosConnector = None
    AptosNetworkManager = None

try:
    from .seedify_imc import AptosIMCManager, RealIMCStrategy
except ImportError:
    AptosIMCManager = None
    RealIMCStrategy = None

try:
    from .airdrop import AptosAirdropFarmer, Aptos2024Strategy
except ImportError:
    AptosAirdropFarmer = None
    Aptos2024Strategy = None

try:
    from .simple_trader import SimpleAptosTrader
except ImportError:
    SimpleAptosTrader = None

try:
    from .premium import AptosLaunchDetector, AptosVolumeFarmer, AptosOpportunityScanner
except ImportError:
    AptosLaunchDetector = None
    AptosVolumeFarmer = None
    AptosOpportunityScanner = None

# Export available strategies
__all__ = [
    'AptosProfitBot',
    'AptosBotReferralSystem', 
    'AptosRevenueCalculator',
    'AutomatedTradingEngine',
    'GridTradingEngine',
    'AptosEcosystem',
    'AptosConnector',
    'AptosNetworkManager',
    'AptosIMCManager',
    'RealIMCStrategy',
    'AptosAirdropFarmer',
    'Aptos2024Strategy',
    'SimpleAptosTrader',
    'AptosLaunchDetector',
    'AptosVolumeFarmer',
    'AptosOpportunityScanner'
]

# Strategy registry for dynamic loading
AVAILABLE_STRATEGIES = {}

if AptosProfitBot:
    AVAILABLE_STRATEGIES['profit_bot'] = AptosProfitBot
if AutomatedTradingEngine:
    AVAILABLE_STRATEGIES['automated_trading'] = AutomatedTradingEngine
if GridTradingEngine:
    AVAILABLE_STRATEGIES['grid_trading'] = GridTradingEngine
if AptosEcosystem:
    AVAILABLE_STRATEGIES['aptos_ecosystem'] = AptosEcosystem
if AptosAirdropFarmer:
    AVAILABLE_STRATEGIES['airdrop_farming'] = AptosAirdropFarmer
if SimpleAptosTrader:
    AVAILABLE_STRATEGIES['simple_trading'] = SimpleAptosTrader

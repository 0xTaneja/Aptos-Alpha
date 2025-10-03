"""
Aptos Alpha Bot - Core Aptos blockchain integration
Equivalent to Hyperliquid SDK but for Aptos
"""

from .api import AptosAPI
from .info import AptosInfo
from .exchange import AptosExchange

__all__ = [
    "AptosAPI",
    "AptosInfo", 
    "AptosExchange"
]

__version__ = "1.0.0"

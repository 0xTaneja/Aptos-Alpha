"""
Sponsor Integrations Module

This module contains integrations with hackathon sponsor protocols:
- Merkle Trade: Perpetuals trading
- Kana Labs: Futures and funding arbitrage
- Panora Exchange: DEX aggregator
- Hyperion: Oracle and indexing
"""

from .merkle_perps import MerklePerpetuals
from .kana_futures import KanaFutures

__all__ = [
    "MerklePerpetuals",
    "KanaFutures"
]

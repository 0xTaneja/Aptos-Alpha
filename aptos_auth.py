"""
Production-grade Aptos authentication module with wallet support
Equivalent to Hyperliquid auth but for Aptos blockchain
"""
import json
import os
import logging
import time
from typing import Tuple, Dict, Optional, Any

from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient

from aptos.exchange import AptosExchange
from aptos.info import AptosInfo

# Configure logging
logger = logging.getLogger(__name__)

class AptosAuth:
    """Secure Aptos authentication with wallet support"""
    
    def __init__(
        self, 
        config_dir: str = ".",
        config_file: str = "config.json",
        wallet_config_file: str = "wallet_config.json",
        network: str = "testnet",
        auto_reconnect: bool = True,
        reconnect_interval: int = 300,  # 5 minutes
        max_retries: int = 3
    ):
        self.config_dir = os.path.abspath(config_dir)
        self.config_path = os.path.join(self.config_dir, config_file)
        self.wallet_config_path = os.path.join(self.config_dir, wallet_config_file)
        
        # Network settings
        self.network = network
        if network == "mainnet":
            self.node_url = "https://fullnode.mainnet.aptoslabs.com/v1"
            self.faucet_url = None
        else:
            self.node_url = "https://fullnode.testnet.aptoslabs.com/v1"
            self.faucet_url = "https://faucet.testnet.aptoslabs.com"
        
        # Connection state
        self.account = None
        self.address = None
        self.info = None
        self.exchange = None
        self.connected = False
        self.last_connected = 0
        self.connection_attempts = 0
        
        # Reconnection settings
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.max_retries = max_retries
        
        logger.info(f"Initialized Aptos Auth for {network} network")
    
    async def connect(self, force_refresh: bool = False) -> Tuple[str, AptosInfo, AptosExchange]:
        """
        Connect to Aptos network with wallet authentication
        
        Args:
            force_refresh: Force a new connection even if recently connected
            
        Returns:
            Tuple of (address, info, exchange)
            
        Raises:
            ValueError: If authentication fails
            ConnectionError: If API connection fails
        """
        # Check if already connected and not forced refresh
        current_time = time.time()
        if (
            self.connected and 
            self.address and self.info and self.exchange and
            not force_refresh and 
            (current_time - self.last_connected) < self.reconnect_interval
        ):
            logger.debug(f"Using existing connection for {self.address} on {self.network}")
            return self.address, self.info, self.exchange
        
        # Reset connection state
        self.connected = False
        if not (self.address and self.info and self.exchange and force_refresh):
            self.connection_attempts += 1
        
        if self.connection_attempts > self.max_retries:
            self.connection_attempts = 0
            logger.error(f"Failed to connect to {self.network} after {self.max_retries} attempts")
            raise ConnectionError(f"Failed to connect to {self.network} after {self.max_retries} attempts")
        
        try:
            logger.info(f"Attempting to connect to {self.network}. Attempt {self.connection_attempts}/{self.max_retries}")
            
            # Try wallet authentication
            if os.path.exists(self.wallet_config_path):
                logger.info(f"Wallet config found at {self.wallet_config_path}. Attempting wallet connection")
                result = await self._connect_with_wallet()
                if result:
                    self.address, self.info, self.exchange = result
                    self.connected = True
                    self.last_connected = current_time
                    self.connection_attempts = 0
                    logger.info(f"Successfully connected with wallet {self.address} on {self.network}")
                    return self.address, self.info, self.exchange
            
            # Try main config authentication
            if os.path.exists(self.config_path):
                logger.info(f"Main config found at {self.config_path}. Attempting main connection")
                result = await self._connect_with_main_config()
                if result:
                    self.address, self.info, self.exchange = result
                    self.connected = True
                    self.last_connected = current_time
                    self.connection_attempts = 0
                    logger.info(f"Successfully connected with main config {self.address} on {self.network}")
                    return self.address, self.info, self.exchange
            
            # Generate new wallet if no config exists
            logger.info("No configuration found. Generating new wallet")
            result = await self._generate_new_wallet()
            if result:
                self.address, self.info, self.exchange = result
                self.connected = True
                self.last_connected = current_time
                self.connection_attempts = 0
                logger.info(f"Successfully connected with new wallet {self.address} on {self.network}")
                return self.address, self.info, self.exchange
            
            raise ConnectionError("Failed to establish any connection method")
            
        except Exception as e:
            logger.error(f"Connection attempt {self.connection_attempts} failed: {e}")
            if self.connection_attempts >= self.max_retries:
                self.connection_attempts = 0
                raise ConnectionError(f"Failed to connect after {self.max_retries} attempts: {e}")
            raise
    
    async def _connect_with_wallet(self) -> Optional[Tuple[str, AptosInfo, AptosExchange]]:
        """Connect using wallet configuration"""
        try:
            with open(self.wallet_config_path, 'r') as f:
                wallet_config = json.load(f)
            
            private_key = wallet_config.get('private_key')
            if not private_key:
                logger.error("No private key found in wallet config")
                return None
            
            # Create account from private key
            self.account = Account.load_key(private_key)
            self.address = str(self.account.address())
            
            # Initialize info and exchange
            self.info = AptosInfo(self.node_url)
            self.exchange = AptosExchange(self.account, self.node_url)
            
            # Test connection
            await self._test_connection()
            
            logger.info(f"Wallet connection successful for {self.address}")
            return self.address, self.info, self.exchange
            
        except Exception as e:
            logger.error(f"Wallet connection failed: {e}")
            return None
    
    async def _connect_with_main_config(self) -> Optional[Tuple[str, AptosInfo, AptosExchange]]:
        """Connect using main configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            aptos_config = config.get('aptos', {})
            private_key = aptos_config.get('admin_private_key')
            
            if not private_key:
                logger.error("No private key found in main config")
                return None
            
            # Create account from private key
            self.account = Account.load_key(private_key)
            self.address = str(self.account.address())
            
            # Initialize info and exchange
            self.info = AptosInfo(self.node_url)
            self.exchange = AptosExchange(self.account, self.node_url)
            
            # Test connection
            await self._test_connection()
            
            logger.info(f"Main config connection successful for {self.address}")
            return self.address, self.info, self.exchange
            
        except Exception as e:
            logger.error(f"Main config connection failed: {e}")
            return None
    
    async def _generate_new_wallet(self) -> Optional[Tuple[str, AptosInfo, AptosExchange]]:
        """Generate new wallet and save configuration"""
        try:
            # Generate new account
            self.account = Account.generate()
            self.address = str(self.account.address())
            
            # Save wallet configuration
            wallet_config = {
                'address': self.address,
                'private_key': self.account.private_key.hex(),
                'public_key': self.account.public_key.hex(),
                'network': self.network,
                'created_at': int(time.time())
            }
            
            with open(self.wallet_config_path, 'w') as f:
                json.dump(wallet_config, f, indent=2)
            
            logger.info(f"New wallet configuration saved to {self.wallet_config_path}")
            
            # Initialize info and exchange
            self.info = AptosInfo(self.node_url)
            self.exchange = AptosExchange(self.account, self.node_url)
            
            # Test connection
            await self._test_connection()
            
            # Fund account from faucet if on testnet
            if self.network == "testnet" and self.faucet_url:
                await self._fund_from_faucet()
            
            logger.info(f"New wallet generated and connected: {self.address}")
            return self.address, self.info, self.exchange
            
        except Exception as e:
            logger.error(f"New wallet generation failed: {e}")
            return None
    
    async def _test_connection(self):
        """Test the connection by getting account info"""
        try:
            if not self.info:
                raise ValueError("Info client not initialized")
            
            # Test connection by getting ledger info
            ledger_info = await self.info.get_ledger_info()
            if not ledger_info:
                raise ConnectionError("Failed to get ledger information")
            
            # Get account balance to verify account exists
            balance = await self.info.get_account_balance(self.address)
            logger.info(f"Account balance: {balance / 100000000:.8f} APT")
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    async def _fund_from_faucet(self, amount: int = 100000000):  # 1 APT
        """Fund account from testnet faucet"""
        try:
            if not self.faucet_url:
                logger.warning("No faucet URL available")
                return
            
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                faucet_request = {
                    "address": self.address,
                    "amount": amount
                }
                
                async with session.post(self.faucet_url, json=faucet_request) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Faucet funding successful: {result}")
                    else:
                        logger.warning(f"Faucet funding failed: {response.status}")
                        
        except Exception as e:
            logger.warning(f"Faucet funding failed: {e}")
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get comprehensive account information"""
        try:
            if not self.connected or not self.info:
                raise ValueError("Not connected to Aptos network")
            
            # Get basic account info
            account_info = await self.info.get_account_info(self.address)
            
            # Get portfolio
            portfolio = await self.info.get_account_portfolio(self.address)
            
            # Get staking info
            staking_info = await self.info.get_staking_info(self.address)
            
            return {
                'address': self.address,
                'network': self.network,
                'account_info': account_info,
                'portfolio': portfolio,
                'staking_info': staking_info,
                'connected_at': self.last_connected,
                'connection_attempts': self.connection_attempts
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}
    
    async def reconnect(self) -> bool:
        """Attempt to reconnect if auto_reconnect is enabled"""
        if not self.auto_reconnect:
            return False
        
        try:
            await self.connect(force_refresh=True)
            return True
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.connected and self.address and self.info and self.exchange
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status"""
        return {
            'connected': self.connected,
            'address': self.address,
            'network': self.network,
            'node_url': self.node_url,
            'last_connected': self.last_connected,
            'connection_attempts': self.connection_attempts,
            'auto_reconnect': self.auto_reconnect
        }
    
    async def close(self):
        """Clean up connections"""
        try:
            if self.info:
                await self.info.close()
            if self.exchange:
                await self.exchange.close()
            
            self.connected = False
            self.address = None
            self.info = None
            self.exchange = None
            
            logger.info("Aptos authentication closed")
            
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

# Convenience function for quick setup
async def setup_aptos_auth(
    config_dir: str = ".",
    network: str = "testnet",
    auto_reconnect: bool = True
) -> Tuple[str, AptosInfo, AptosExchange]:
    """
    Quick setup function for Aptos authentication
    
    Returns:
        Tuple of (address, info, exchange)
    """
    auth = AptosAuth(
        config_dir=config_dir,
        network=network,
        auto_reconnect=auto_reconnect
    )
    
    return await auth.connect()

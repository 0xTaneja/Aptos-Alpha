"""
Background Task Manager for Aptos Trading Bot
Manages background tasks for trading operations, monitoring, and maintenance
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from aptos_sdk.async_client import RestClient
from aptos_sdk.account import Account

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """
    Manages background tasks for Aptos trading operations
    Handles periodic tasks like balance monitoring, position updates, and maintenance
    """
    
    def __init__(self, aptos_client: RestClient):
        self.client = aptos_client
        self.tasks = {}  # {task_id: task_info}
        self.running_tasks = {}  # {task_id: asyncio.Task}
        self.is_running = False
        self.task_counter = 0
        
    async def start(self):
        """Start the background task manager"""
        self.is_running = True
        logger.info("Background Task Manager started")
        
    async def stop(self):
        """Stop all background tasks"""
        self.is_running = False
        
        # Cancel all running tasks
        for task_id, task in self.running_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        self.running_tasks.clear()
        logger.info("Background Task Manager stopped")
        
    def add_periodic_task(self, 
                         name: str, 
                         func: Callable, 
                         interval: int, 
                         *args, 
                         **kwargs) -> str:
        """
        Add a periodic task
        
        Args:
            name: Task name
            func: Function to execute
            interval: Interval in seconds
            *args, **kwargs: Arguments for the function
            
        Returns:
            Task ID
        """
        task_id = f"task_{self.task_counter}"
        self.task_counter += 1
        
        task_info = {
            "id": task_id,
            "name": name,
            "func": func,
            "interval": interval,
            "args": args,
            "kwargs": kwargs,
            "created_at": datetime.now(),
            "last_run": None,
            "run_count": 0,
            "error_count": 0
        }
        
        self.tasks[task_id] = task_info
        
        # Start the task if manager is running
        if self.is_running:
            self.running_tasks[task_id] = asyncio.create_task(
                self._run_periodic_task(task_info)
            )
            
        logger.info(f"Added periodic task '{name}' with {interval}s interval")
        return task_id
        
    def add_delayed_task(self, 
                        name: str, 
                        func: Callable, 
                        delay: int, 
                        *args, 
                        **kwargs) -> str:
        """
        Add a one-time delayed task
        
        Args:
            name: Task name
            func: Function to execute
            delay: Delay in seconds
            *args, **kwargs: Arguments for the function
            
        Returns:
            Task ID
        """
        task_id = f"delayed_{self.task_counter}"
        self.task_counter += 1
        
        task_info = {
            "id": task_id,
            "name": name,
            "func": func,
            "delay": delay,
            "args": args,
            "kwargs": kwargs,
            "created_at": datetime.now(),
            "type": "delayed"
        }
        
        self.tasks[task_id] = task_info
        
        # Start the task if manager is running
        if self.is_running:
            self.running_tasks[task_id] = asyncio.create_task(
                self._run_delayed_task(task_info)
            )
            
        logger.info(f"Added delayed task '{name}' with {delay}s delay")
        return task_id
        
    async def _run_periodic_task(self, task_info: Dict):
        """Run a periodic task"""
        task_id = task_info["id"]
        name = task_info["name"]
        func = task_info["func"]
        interval = task_info["interval"]
        args = task_info["args"]
        kwargs = task_info["kwargs"]
        
        logger.debug(f"Starting periodic task '{name}'")
        
        while self.is_running:
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
                    
                # Update task info
                task_info["last_run"] = datetime.now()
                task_info["run_count"] += 1
                
                logger.debug(f"Periodic task '{name}' completed successfully")
                
            except Exception as e:
                task_info["error_count"] += 1
                logger.error(f"Error in periodic task '{name}': {e}")
                
            # Wait for next interval
            await asyncio.sleep(interval)
            
        logger.debug(f"Periodic task '{name}' stopped")
        
    async def _run_delayed_task(self, task_info: Dict):
        """Run a delayed task"""
        name = task_info["name"]
        func = task_info["func"]
        delay = task_info["delay"]
        args = task_info["args"]
        kwargs = task_info["kwargs"]
        
        logger.debug(f"Starting delayed task '{name}' with {delay}s delay")
        
        # Wait for delay
        await asyncio.sleep(delay)
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
                
            logger.debug(f"Delayed task '{name}' completed successfully")
            
        except Exception as e:
            logger.error(f"Error in delayed task '{name}': {e}")
            
    def remove_task(self, task_id: str) -> bool:
        """Remove a task"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            if not task.done():
                task.cancel()
            del self.running_tasks[task_id]
            
        if task_id in self.tasks:
            task_name = self.tasks[task_id]["name"]
            del self.tasks[task_id]
            logger.info(f"Removed task '{task_name}' ({task_id})")
            return True
            
        return False
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a task"""
        if task_id not in self.tasks:
            return None
            
        task_info = self.tasks[task_id].copy()
        
        # Add runtime status
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task_info["status"] = "running" if not task.done() else "completed"
            task_info["is_cancelled"] = task.cancelled()
        else:
            task_info["status"] = "not_started"
            
        return task_info
        
    def list_tasks(self) -> List[Dict]:
        """List all tasks with their status"""
        return [self.get_task_status(task_id) for task_id in self.tasks.keys()]
        
    async def monitor_aptos_balance(self, account: Account, threshold: float = 0.1):
        """Monitor Aptos account balance and alert if below threshold"""
        try:
            balance = await self.client.account_balance(str(account.address()))
            balance_apt = balance / 100000000  # Convert octas to APT
            
            if balance_apt < threshold:
                logger.warning(f"Low balance alert: {balance_apt:.6f} APT (threshold: {threshold} APT)")
                
        except Exception as e:
            logger.error(f"Error monitoring balance for {account.address()}: {e}")
            
    async def monitor_network_status(self):
        """Monitor Aptos network status"""
        try:
            # Get ledger info to check network health
            ledger_info = await self.client.ledger_info()
            current_time = time.time()
            ledger_timestamp = int(ledger_info["ledger_timestamp"]) / 1000000  # Convert microseconds
            
            # Check if network is lagging (more than 30 seconds behind)
            time_diff = current_time - ledger_timestamp
            if time_diff > 30:
                logger.warning(f"Network lag detected: {time_diff:.2f} seconds behind")
                
        except Exception as e:
            logger.error(f"Error monitoring network status: {e}")
            
    async def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks"""
        current_time = datetime.now()
        tasks_to_remove = []
        
        for task_id, task_info in self.tasks.items():
            # Skip running tasks
            if task_id in self.running_tasks and not self.running_tasks[task_id].done():
                continue
                
            # Check if task is old enough
            created_at = task_info["created_at"]
            age = current_time - created_at
            
            if age > timedelta(hours=max_age_hours):
                tasks_to_remove.append(task_id)
                
        # Remove old tasks
        for task_id in tasks_to_remove:
            self.remove_task(task_id)
            
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")

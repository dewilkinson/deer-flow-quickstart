"""
PROJECT COBALT: CORE RESOURCE TYPE
RESOURCE: Asset-Bucket Engine
VERSION: 1.1.0

PROBLEM STATEMENT:
    Traders need to bundle assets and apply specific logic sequences at specific 
    times. A 'watchlist' needs a simple quote every 5m, while an 'intelligence 
    briefing' needs a deep SMC/Sentiment scan once every 24h.

UPDATES IN V1.1.0:
    - Added 'display_name' field for enhanced UI metadata.
    - Updated 'interval' logic to support delay-based 'ONE_SHOT' triggers.
    - Asynchronous operational core connected to real finance tools.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from src.tools import (
    get_macd_analysis,
    get_rsi_analysis,
    get_smc_analysis,
    get_stock_quote,
)

logger = logging.getLogger(__name__)


class AssetBucket:
    def __init__(self, bucket_id: str, display_name: str, vault_path: str = None):
        self.bucket_id = bucket_id
        # Use OBSIDIAN_VAULT_PATH from env, or the passed vault_path, or current directory
        self.vault_path = vault_path or os.environ.get("OBSIDIAN_VAULT_PATH", "./")
        
        self.config_path = os.path.join(self.vault_path, "_cobalt", "06_Resources", "Buckets", f"{bucket_id}_config.json")
        self.state_path = os.path.join(self.vault_path, "_cobalt", "01_Transit", "Buckets", f"{bucket_id}_state.json")
        
        # Default Configuration
        self.config = {
            "bucket_id": bucket_id,
            "display_name": display_name,
            "assets": [],
            "operations": ["QUOTE"],
            "update_mode": "MANUAL",
            "interval": 60,  # Frequency for periodic; Delay for one-shot
            "display_columns": ["Ticker", "Price", "Change %"]
        }
        self.load_config()

    def load_config(self):
        """Loads configuration from the vault if it exists."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                try:
                    self.config.update(json.load(f))
                except json.JSONDecodeError as e:
                    logger.error(f"AssetBucket [{self.bucket_id}]: Failed to parse config - {e}")

    def save_config(self):
        """Persists bucket configuration and triggers scheduler sync."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)
        self._sync_with_external_scheduler()

    def _sync_with_external_scheduler(self):
        """
        Placeholder for communicating with an external scheduler.
        Pending custom crontab spec implementation.
        """
        mode = self.config.get("update_mode", "MANUAL")
        interval = self.config.get("interval", 60)
        
        if mode == "PERIODIC":
            logger.info(f"⏰ Scheduler (Dormant): Registering recurring task for {self.bucket_id} every {interval}m.")
        elif mode == "ONE_SHOT":
            logger.info(f"⏲️ Scheduler (Dormant): Registering single trigger for {self.bucket_id} in {interval}m.")

    async def update(self) -> Dict[str, Any]:
        """Iterates through assets concurrently and applies the operation sequence."""
        display_name = self.config.get("display_name", self.bucket_id)
        assets = self.config.get("assets", [])
        logger.info(f"🪣 Systemic Update Triggered: Bucket '{display_name}' ({len(assets)} assets)...")

        # Gather tasks and run them concurrently
        tasks = [self._process_single_asset(asset) for asset in assets]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for asset, result in zip(assets, results_list):
            if isinstance(result, Exception):
                logger.error(f"AssetBucket [{self.bucket_id}] error processing {asset}: {result}")
                results[asset] = {"Ticker": asset, "Error": str(result), "Status": "FAILED"}
            else:
                results[asset] = result

        self._persist_state(results)
        return results

    async def _process_single_asset(self, asset: str) -> Dict[str, Any]:
        """Wrapper to evaluate all operations sequentially for a single asset."""
        asset_results = {"Ticker": asset, "Status": "OK"}
        operations = self.config.get("operations", [])

        for op in operations:
            try:
                op_result = await self._execute_op(asset, op)
                if isinstance(op_result, dict):
                    asset_results.update(op_result)
            except Exception as e:
                logger.warning(f"Operation '{op}' failed on '{asset}': {e}")
                asset_results[f"{op}_Error"] = str(e)
                asset_results["Status"] = "PARTIAL"

        return asset_results

    async def _execute_op(self, asset: str, op: str) -> Dict[str, Any]:
        """Dispatches the operation to the relevant Cobalt async tool."""
        op_upper = str(op).strip().upper()
        
        if op_upper == "QUOTE":
            # get_stock_quote returns Dict[str, Any] or str
            quote_data = await get_stock_quote.ainvoke({"ticker": asset, "use_fast_path": True, "force_refresh": True})
            if isinstance(quote_data, dict):
                return {
                    "Price": quote_data.get("price", "N/A"),
                    "Change %": quote_data.get("change", "N/A"),
                    "Volume": quote_data.get("volume", "N/A")
                }
            return {"QUOTE_Result": quote_data}
            
        elif op_upper == "SMC_SCAN":
            res = await get_smc_analysis.ainvoke({"ticker": asset})
            # Extrapolate top level trend or value
            return res if isinstance(res, dict) else {"SMC_Raw": str(res)}
            
        elif op_upper == "RSI":
            res = await get_rsi_analysis.ainvoke({"ticker": asset})
            if isinstance(res, dict):
                return {"RSI_14": res.get("rsi", "N/A"), "RSI_Signal": res.get("signal", "N/A")}
            return {"RSI_Raw": str(res)}
            
        elif op_upper == "MACD":
            res = await get_macd_analysis.ainvoke({"ticker": asset})
            if isinstance(res, dict):
                return {"MACD": res.get("macd", "N/A"), "MACD_Signal": res.get("signal", "N/A")}
            return {"MACD_Raw": str(res)}
        
        else:
            logger.debug(f"Unknown operation directive '{op}'")
            return {f"{op}_Unknown": True}

    def _persist_state(self, results: Dict[str, Any]):
        """Saves current data for visualization into the Vault transit directory."""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        state_payload = {
            "last_updated": datetime.now().isoformat(),
            "display_name": self.config.get("display_name", self.bucket_id),
            "columns": self.config.get("display_columns", []),
            "data": results
        }
        try:
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(state_payload, f, indent=4)
            logger.info(f"✅ AssetBucket [{self.bucket_id}] state persisted transitively to {os.path.basename(self.state_path)}")
        except Exception as e:
            logger.error(f"AssetBucket [{self.bucket_id}] failed to persist state: {e}")

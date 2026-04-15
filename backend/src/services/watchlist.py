from enum import Enum
from typing import Optional
from src.services.asset_bucket import AssetBucket

class ExecutionPriority(str, Enum):
    BACKGROUND = "PRIORITY_BACKGROUND"
    LOW = "PRIORITY_LOW"
    NORMAL = "PRIORITY_NORMAL"
    HIGH = "PRIORITY_HIGH"
    CRITICAL = "PRIORITY_CRITICAL"

class Watchlist(AssetBucket):
    """
    A specific archetype of AssetBucket designed to monitor a list of assets
    with tiered refresh cycles (e.g. 1m prices, 5m OCHL blocks).
    """
    def __init__(self, bucket_id: str, display_name: str, priority: ExecutionPriority = ExecutionPriority.NORMAL, vault_path: Optional[str] = None):
        super().__init__(bucket_id, display_name, vault_path)
        
        # Override fundamental properties to match the Watchlist Class archetype
        self.config["bucket_class"] = "watchlist"
        self.config["priority"] = priority.value
        self.config["update_mode"] = "PERIODIC"
        
        # Apply Watchlist defaults if initializing a naked bucket logic structure
        if not self.config.get("assets"):
            self.config["assets"] = []
            
        # If operations are still the AssetBucket defaults ("QUOTE"), upgrade to the Macro template
        if self.config.get("operations") == ["QUOTE"] or not self.config.get("operations"):
            self.config["operations"] = {
                "FETCH_PRICE": {"interval": 1},
                "FETCH_OCHL": {"interval": 5},
                "FETCH_VP": {"interval": 5},
                "CALC_REGIME": {"interval": 5},
                "CALC_SORTINO": {"interval": 5}
            }

            
        # Adjust display columns for UI rendering
        if self.config.get("display_columns") == ["Ticker", "Price", "Change %"] or not self.config.get("display_columns"):
            self.config["display_columns"] = ["Ticker", "Price", "Volume", "Regime", "Sortino"]

        # Commit initial template to Obsidian resources
        self.save_config()

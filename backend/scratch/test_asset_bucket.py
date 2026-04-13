import asyncio
import logging
import os

# Set dummy env vars for tests if not present
if not os.environ.get("OBSIDIAN_VAULT_PATH"):
    os.environ["OBSIDIAN_VAULT_PATH"] = "./test_vault"

from src.services.asset_bucket import AssetBucket

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    print("Initializing Asset Bucket...")
    # Initialize the bucket
    bucket = AssetBucket(bucket_id="TEST_TECH", display_name="Megacap Tech Daily")
    
    # Override configuration for test
    bucket.config["assets"] = ["NVDA", "AAPL", "MSFT"]
    bucket.config["operations"] = ["QUOTE", "SMC_SCAN"]
    bucket.config["display_columns"] = ["Ticker", "Price", "Change %", "SMC_Trend"]
    
    print(f"Bucket Configured. Saving to {bucket.config_path}...")
    bucket.save_config()
    
    print("Running asynchronous bucket update across all assets...")
    results = await bucket.update()
    
    print("\n--- RESULTS ---")
    for asset, data in results.items():
        print(f"{asset}: {data}")
        
    print(f"\nState has been persisted to {bucket.state_path}")

if __name__ == "__main__":
    asyncio.run(main())

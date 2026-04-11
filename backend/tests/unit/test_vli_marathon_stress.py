import asyncio
import random
import time
import logging
import json
from datetime import datetime, timedelta
from src.services.datastore import DatastoreManager
from src.services.heat_manager import HeatManager
from src.config.database import PersistentCache, get_session_local

# Configuration
DURATION_MINUTES = 45
TPS = 5 # Transactions Per Second (simulated)
TOTAL_REQS = DURATION_MINUTES * 60 * TPS
SYMBOLS_POOL_SIZE = 1500 # Forces LRU eviction (max 1000)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("VLI-STRESS-MARATHON")

async def run_marathon():
    logger.info(f"Initiating VLI-CACHE-STRESS-45 Marathon...")
    logger.info(f"Target Duration: {DURATION_MINUTES}m | Pool: {SYMBOLS_POOL_SIZE} symbols | Target Reqs: {TOTAL_REQS}")
    
    start_time = time.time()
    end_time = start_time + (DURATION_MINUTES * 60)
    
    req_count = 0
    hit_count = 0
    drift_triggers = 0
    
    # 1. Start background workers
    DatastoreManager.ensure_worker_started()
    
    # Symbols with their "Sticky" reference price to trigger drift
    symbol_ref_prices = {f"SYM_{i}": 100.0 for i in range(SYMBOLS_POOL_SIZE)}
    
    try:
        while time.time() < end_time:
            # Batch of 10 requests every loop iteration
            for _ in range(10):
                req_count += 1
                ticker = f"SYM_{random.randint(0, SYMBOLS_POOL_SIZE - 1)}"
                resource = random.choice(["history", "analysis", "news"])
                tf = random.choice(["1h", "4h", "1d"])
                
                # Randomized "Market Price" - 5% chance of severe drift (>1%)
                base_price = symbol_ref_prices[ticker]
                if random.random() < 0.05:
                    current_price = base_price * (1.0 + (random.uniform(0.015, 0.05) * random.choice([1, -1])))
                    drift_triggers += 1
                else:
                    current_price = base_price * (1.0 + random.uniform(-0.005, 0.005))

                # Operation: Get or Store
                if random.random() < 0.7: # 70% Read
                    artifact = DatastoreManager.get_artifact(ticker, resource, tf)
                    if artifact:
                        hit_count += 1
                else: # 30% Store
                    DatastoreManager.store_artifact(
                        ticker, resource, tf, 
                        f"Synthetic report for {ticker} @ {datetime.now()}", 
                        price=current_price
                    )
            
            # Monitoring every 10 seconds
            if req_count % 100 == 0:
                elapsed = time.time() - start_time
                done_pct = (elapsed / (DURATION_MINUTES * 60)) * 100
                hit_rate = (hit_count / req_count) * 100 if req_count > 0 else 0
                
                from src.tools.shared_storage import history_cache
                logger.info(f"Progress: {done_pct:.1f}% | Reqs: {req_count} | Hits: {hit_count} ({hit_rate:.1f}%) | Drift Purges: {drift_triggers} | RAM Tickers: {len(history_cache)}")
                
            await asyncio.sleep(1.0 / TPS) # Control the pace
            
    except KeyboardInterrupt:
        logger.warning("Marathon interrupted by user.")
    except Exception as e:
        logger.error(f"Marathon crashed: {e}")
    finally:
        total_time = time.time() - start_time
        logger.info("=== MARATHON COMPLETE ===")
        logger.info(f"Total Time: {total_time/60:.1f} minutes")
        logger.info(f"Total Requests: {req_count}")
        logger.info(f"Total Hits: {hit_count} ({ (hit_count/req_count)*100 if req_count > 0 else 0:.1f}%)")
        logger.info(f"Drift Purges triggered: {drift_triggers}")
        
        # Verify persistence at end
        SessionLocal = get_session_local()
        with SessionLocal() as db:
            db_count = db.query(PersistentCache).count()
            logger.info(f"Final DB Record Count: {db_count}")

if __name__ == "__main__":
    asyncio.run(run_marathon())

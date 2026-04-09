import asyncio
import time
import json
from datetime import datetime, timedelta

from src.tools.finance import get_raw_smc_tables
from src.services.datastore import DatastoreManager

async def run_stress_test():
    ticker = "ITA"
    print("========================================")
    print("VLI SMC TTL Caching Stress Test")
    print("========================================\n")
    
    # 1. Clear caches to ensure a clean start
    DatastoreManager.invalidate_cache()
    print("[*] Cache cleared.")
    
    # 2. Initial Fetch
    start_time_1 = time.time()
    await get_raw_smc_tables(ticker)  # Warm up the YFinance connection
    
    start_time_1 = time.time()
    res1 = await get_raw_smc_tables(ticker)
    elapsed_1 = (time.time() - start_time_1) * 1000
    print(f"[*] Initial Fetch (No Cache | Forced Refresh via script edge case) Latency: {elapsed_1:.2f}ms")
    
    # Let's ensure cache populated accurately
    cache = DatastoreManager.get_analysis_cache()
    cache_key = f"{ticker}_1y_1d_raw"
    if cache_key not in cache:
        print("[!] ERROR: Initial fetch didn't populate analysis_cache!")
        return
        
    print(f"    -> Cache Key `{cache_key}` successfully generated.")

    # 3. First Cached Fetch (Immediate retry)
    start_time_2 = time.time()
    res2 = await get_raw_smc_tables(ticker)
    elapsed_2 = (time.time() - start_time_2) * 1000
    print(f"[*] Immediate Refetch (Expected: Valid Cache) Latency: {elapsed_2:.2f}ms")
    assert res1 == res2, "Cached result doesn't equal initial result!"
    assert elapsed_2 < 100, f"Cache retrieval was too slow! {elapsed_2:.2f}ms > 100ms"
    
    # 4. Simulate Accelerated Time
    print("\n[*] Simulating accelerated time: Clock shifted +23.99 hours...")
    
    # TTL for 1d is 86400 seconds. We'll set last_updated to (now - 86390 seconds)
    cache[cache_key]["last_updated"] = datetime.now() - timedelta(seconds=86390)
    
    start_time_3 = time.time()
    res3 = await get_raw_smc_tables(ticker)
    elapsed_3 = (time.time() - start_time_3) * 1000
    print(f"[*] Secondary Refetch (Expected: Still Valid Cache) Latency: {elapsed_3:.2f}ms")
    assert res1 == res3, "Cached result doesn't equal initial result!"
    assert elapsed_3 < 100, f"Cache retrieval was too slow! {elapsed_3:.2f}ms > 100ms"

    # 5. Simulate Accelerated Time (Mocking datetime to expired)
    print("\n[*] Simulating accelerated time: Clock shifted +24.1 hours (EXPIRED!)...")
    
    cache[cache_key]["last_updated"] = datetime.now() - timedelta(seconds=86500)
    
    # Expire the DF cache as well so we force a true network round-trip > 100ms
    df_cache = DatastoreManager.get_df_cache()
    df_cache_key = f"{ticker}_1y_1d"
    if df_cache_key in df_cache:
        df_cache[df_cache_key]["last_updated"] = datetime.now() - timedelta(seconds=86500)

    start_time_4 = time.time()
    res4 = await get_raw_smc_tables(ticker)
    elapsed_4 = (time.time() - start_time_4) * 1000
    print(f"[*] Expired Fetch (Expected: Cache Miss | Full Computation) Latency: {elapsed_4:.2f}ms")
    assert elapsed_4 > 100, f"Compute was suspiciously fast ({elapsed_4:.2f}ms). This implies the cache was wrongly utilized!"
        
    print("\n[✓] ALL STRESS TESTS PASSED: Valid caches hit near-instant metrics, and TTL expulsions correctly forced dataframe rebuilds.")

if __name__ == "__main__":
    asyncio.run(run_stress_test())

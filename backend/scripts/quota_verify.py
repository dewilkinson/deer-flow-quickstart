import asyncio
import os
import sys

# Ensure the backend src is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llms.llm import get_llm_by_type
from src.utils.quota_shield import VLIQuotaExhaustedError, quota_shield

async def test_quota_shield():
    print("Initializing Quota Shield Stress Test...")
    
    # Set a very low limit for 'reasoning' to trigger failure fast
    bucket = quota_shield.get_bucket("reasoning")
    bucket.rpm_limit = 2
    bucket.tpm_limit = 5000
    
    llm = get_llm_by_type("reasoning")
    print(f"Model: {getattr(llm, 'model_name', 'Reasoning')}")
    
    try:
        print("Call 1: Expect Success")
        await llm.ainvoke("Hello")
        print("Call 1 Success")
        
        print("Call 2: Expect Success")
        await llm.ainvoke("Hello again")
        print("Call 2 Success")
        
        print("Call 3: Expect Shield Block (Fail-Fast)")
        await llm.ainvoke("This should fail")
        print("Error: Call 3 passed when it should have been blocked!")
        
    except VLIQuotaExhaustedError as e:
        print(f"Shield Verified: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_quota_shield())

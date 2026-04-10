import asyncio
import sys
import logging
import json

sys.path.insert(0, './')

from src.server.app import _invoke_vli_agent

logging.basicConfig(level=logging.INFO)

async def test_hybrid_mode():
    print("Testing HEADLESS DATA ENGINE mode...")
    res, state = await _invoke_vli_agent(
        text="SMC Analysis for NVDA", 
        image=None, 
        direct_mode=False, 
        raw_data_mode=True, 
        reporter_llm_type="basic"
    )
    
    print("=" * 60)
    print(f"RESPONSE TYPE: {type(res)}")
    print("PAYLOAD PREVIEW (first 500 chars):")
    print(res[:500] if isinstance(res, str) else res)
    print("=" * 60)
    
    try:
        parsed = json.loads(res)
        print(f"Valid JSON! Extracted Array Length: {len(parsed)}")
    except Exception as e:
        print(f"FAILED TO PARSE JSON: {e}")

if __name__ == "__main__":
    asyncio.run(test_hybrid_mode())

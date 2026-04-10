import sys
import os
import asyncio
import time
from pathlib import Path
import logging

logging.basicConfig(level=logging.WARNING)

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.finance import get_stock_quote
from langchain_openai import ChatOpenAI

async def test_tool_calling(model_name: str, timeout: float = 30.0):
    print(f"\n--- Testing {model_name} Tool Calling ---")
    
    llm = ChatOpenAI(
        model=model_name,
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )
    
    print(f"Testing get_stock_quote tool binding with AAPL...")
    llm_with_tools = llm.bind_tools([get_stock_quote])
    
    start = time.perf_counter()
    try:
        res = await asyncio.wait_for(
            llm_with_tools.ainvoke("What is the current stock price of AAPL? Please use get_stock_quote."),
            timeout=timeout
        )
        duration = time.perf_counter() - start
        
        print(f"Response received in {duration:.1f}s")
        if hasattr(res, "tool_calls") and res.tool_calls:
            print(f"SUCCESS: Tool calls generated: {res.tool_calls}")
            return True
        else:
            print("FAILED: No tool calls generated.")
            print(f"Content: {res.content}")
            return False
            
    except asyncio.TimeoutError:
        print(f"FAILED: Request timed out after {timeout} seconds (Automatic Fail).")
        return False
    except Exception as e:
        print(f"FAILED: Exception occurred: {e}")
        return False

async def main():
    print("Executing Local Model Tool-Calling Test (Timeout: 30s)...\n")
    
    # 1. Test gemma4:e4b
    success = await test_tool_calling("gemma4:e4b", 30.0)

if __name__ == "__main__":
    asyncio.run(main())

import sys
import os
import asyncio
import time
from pathlib import Path
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING)

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.finance import get_stock_quote
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

async def test_cloud_tool_calling(model_name: str, timeout: float = 30.0):
    print(f"\n--- Testing Cloud Model {model_name} Tool Calling ---")
    
    api_key = os.getenv("BASIC_MODEL__api_key") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("FAILED: No Google API Key found in environment.")
        return False
        
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0
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
    print("Executing Cloud Model Tool-Calling Test (Timeout: 30s)...\n")
    
    # Test Gemma-4-31b-it on cloud
    success = await test_cloud_tool_calling("gemma-4-31b-it", 30.0)

if __name__ == "__main__":
    asyncio.run(main())

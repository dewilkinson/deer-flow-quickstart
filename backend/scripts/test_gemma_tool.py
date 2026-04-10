import sys
import os
import asyncio
from pathlib import Path
import logging

logging.basicConfig(level=logging.WARNING)

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llms.llm import get_llm_by_type
from src.tools.finance import get_stock_quote

async def test_tool_calling():
    print("--- Testing Gemma 4 Tool Calling ---")
    try:
        llm = get_llm_by_type("core")
        print(f"Loaded LLM type: {type(llm)}")
        
        # Test tool binding
        print("\nTesting get_stock_quote tool binding with AAPL...")
        llm_with_tools = llm.bind_tools([get_stock_quote])
        
        res = await asyncio.wait_for(
            llm_with_tools.ainvoke("What is the current stock price of AAPL? Please use get_stock_quote."),
            timeout=10.0
        )
        
        print("\nResponse from model:")
        print("Content:", res.content)
        
        if hasattr(res, "tool_calls") and res.tool_calls:
            print(f"\nSUCCESS: Tool calls generated: {res.tool_calls}")
            
            # Now let's try actually executing the first tool call to verify the tool itself
            tcall = res.tool_calls[0]
            if tcall['name'] == 'get_stock_quote':
                print(f"\nExecuting tool get_stock_quote with args: {tcall['args']}...")
                # Call tool directly
                tool_res = await get_stock_quote.ainvoke(tcall['args'])
                print(f"Tool execution result: {tool_res}")
        else:
            print("\nFAILED: No tool calls generated. The model might not support tool calling or failed to format it properly.")
            
    except asyncio.TimeoutError:
        print("\nFAILED: Request timed out after 10 seconds.")
    except Exception as e:
        print(f"\nFAILED: Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_calling())

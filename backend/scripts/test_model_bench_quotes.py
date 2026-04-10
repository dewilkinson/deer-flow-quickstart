import sys
import os
import asyncio
import time
import uuid
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.finance import get_stock_quote
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

load_dotenv()

async def benchmark_model(model_name: str, symbols: list[str]) -> list[dict]:
    print(f"\nBenchmarking {model_name}...")
    api_key = os.getenv("BASIC_MODEL__api_key") or os.getenv("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0
    )
    llm_with_tools = llm.bind_tools([get_stock_quote])
    
    results = []
    
    for sym in symbols:
        nonce = uuid.uuid4().hex[:6]
        # Force refresh via prompt instruction as well to be safe
        prompt = f"Get the current stock quote of {sym}. Pass force_refresh=True to the tool. [nonce: {nonce}]"
        
        stages = {"symbol": sym, "tool_latency": None, "fetch_latency": None, "synth_latency": None, "total": None}
        
        try:
            # Stage 1: Tool Call Generation
            start = time.perf_counter()
            res1 = await asyncio.wait_for(llm_with_tools.ainvoke(prompt), timeout=15.0)
            stages["tool_latency"] = time.perf_counter() - start
            
            if hasattr(res1, "tool_calls") and res1.tool_calls:
                tc = res1.tool_calls[0]
                # Enforce uncached fetch
                if "force_refresh" not in tc["args"]:
                    tc["args"]["force_refresh"] = True
                    
                # Stage 2: Tool Execution
                t_start = time.perf_counter()
                tool_result = await get_stock_quote.ainvoke(tc["args"])
                stages["fetch_latency"] = time.perf_counter() - t_start
                
                # Stage 3: Synthesis Generation
                msgs = [
                    HumanMessage(content=prompt),
                    res1,
                    ToolMessage(tool_call_id=tc["id"], tool_call_name=tc["name"], content=str(tool_result))
                ]
                s_start = time.perf_counter()
                res2 = await asyncio.wait_for(llm.ainvoke(msgs), timeout=15.0)
                stages["synth_latency"] = time.perf_counter() - s_start
                
                stages["total"] = stages["tool_latency"] + stages["fetch_latency"] + stages["synth_latency"]
                print(f"  {sym}: Tool={stages['tool_latency']:.2f}s | Fetch={stages['fetch_latency']:.2f}s | Synth={stages['synth_latency']:.2f}s | Total={stages['total']:.2f}s")
            else:
                print(f"  {sym}: (Failed - No tool call)")
        except Exception as e:
            print(f"  {sym}: Failed with exception: {e}")
            
        results.append(stages)
        await asyncio.sleep(0.5)
        
    return results
    
async def main():
    # 10 symbols for our test set
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "AMD", "INTC"]
    
    # 1. Gemma 4 Cloud 
    gemma_results = await benchmark_model("gemma-4-31b-it", symbols)
    
    # 2. Gemini 3 Flash
    gemini_results = await benchmark_model("gemini-3-flash-preview", symbols)
    
    # Print Compare Table
    header = f"{'Sym':<6} | {'Gemma Tool':<10} | {'Gemma Fetch':<11} | {'Gemma Synth':<11} | {'Gemma Total':<11} | {'Flash Tool':<10} | {'Flash Fetch':<11} | {'Flash Synth':<11} | {'Flash Total':<11}"
    print("\n" + "="*len(header))
    print("END-TO-END BENCHMARK RESULTS".center(len(header)))
    print("="*len(header))
    print(header)
    print("-" * len(header))
    
    total_g_tool, total_g_synth, total_g = 0, 0, 0
    total_gem_tool, total_gem_synth, total_gem = 0, 0, 0
    valid_g, valid_gem = 0, 0
    
    for i, sym in enumerate(symbols):
        g = gemma_results[i]
        gem = gemini_results[i]
        
        row = [sym]
        
        if g["total"]:
            row.extend([f"{g['tool_latency']:.2f}s", f"{g['fetch_latency']:.2f}s", f"{g['synth_latency']:.2f}s", f"{g['total']:.2f}s"])
            total_g_tool += g['tool_latency']
            total_g_synth += g['synth_latency']
            total_g += g['total']
            valid_g += 1
        else:
            row.extend(["ERR", "ERR", "ERR", "ERR"])
            
        if gem["total"]:
            row.extend([f"{gem['tool_latency']:.2f}s", f"{gem['fetch_latency']:.2f}s", f"{gem['synth_latency']:.2f}s", f"{gem['total']:.2f}s"])
            total_gem_tool += gem['tool_latency']
            total_gem_synth += gem['synth_latency']
            total_gem += gem['total']
            valid_gem += 1
        else:
            row.extend(["ERR", "ERR", "ERR", "ERR"])
            
        print(f"{sym:<6} | {row[1]:<10} | {row[2]:<11} | {row[3]:<11} | {row[4]:<11} | {row[5]:<10} | {row[6]:<11} | {row[7]:<11} | {row[8]:<11}")
    
    print("-" * len(header))
    
    print("\nPERFORMANCE METRICS (Averages):")
    if valid_g > 0:
        print(f"Gemma 4 (n={valid_g}) -> Tool: {total_g_tool/valid_g:.2f}s | Synth: {total_g_synth/valid_g:.2f}s | Total Avg: {total_g/valid_g:.2f}s")
    if valid_gem > 0:
        print(f"Gemini Flash (n={valid_gem}) -> Tool: {total_gem_tool/valid_gem:.2f}s | Synth: {total_gem_synth/valid_gem:.2f}s | Total Avg: {total_gem/valid_gem:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())

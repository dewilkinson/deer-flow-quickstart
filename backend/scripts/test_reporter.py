import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

from src.llms.llm import get_llm_by_type
from src.prompts.template import apply_prompt_template
from langchain_core.messages import HumanMessage, AIMessage

async def main():
    llm = get_llm_by_type("basic")
    
    msg_content = "Analysis of AAPL reveals a conflict between timeframes and a failure to meet the minimum risk-adjusted return hurdles required for capital deployment. The daily macro structure has a confirmed bearish Change of Character (CHoCH), establishing a higher-timeframe bias against long positions. I'm not a margin trader. I'm a risk-adjusted return trader. I don't want to make money if it means taking the risk of losing it all."
    
    state = {
        "messages": [
            HumanMessage(content="Analyze AAPL"),
            AIMessage(content=msg_content)
        ]
    }
    
    messages = apply_prompt_template("reporter", state)
    with open('reporter_out.txt', 'w', encoding='utf-8') as f:
        f.write("Calling reporter LLM...\n")
        response = await llm.ainvoke(messages)
        f.write(f"Response Metadata: {getattr(response, 'response_metadata', None)}\n")
        f.write(f"Response Text: {str(response.content)}\n")

if __name__ == "__main__":
    asyncio.run(main())

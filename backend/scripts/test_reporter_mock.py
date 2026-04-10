import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from src.graph.nodes.reporter import reporter_node

async def test_reporter_compaction_logic():
    print("--- Testing Reporter Compaction Logic (Mocked LLM) ---")
    
    # 1. Setup mock state with tool-call-only AIMessage
    state = {
        "messages": [
            HumanMessage(content="Analyze ETH"),
            AIMessage(content="", tool_calls=[{"name": "run_smc_analysis", "args": {"ticker": "ETH"}, "id": "call_1"}]),
            ToolMessage(content="SMC Data: BOS detected at $2400", tool_call_id="call_1", name="run_smc_analysis")
        ],
        "final_report": ""
    }
    
    # 2. Mock the LLM and prompt template to prevent live API calls
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="Mocked Synthesis Report")
    
    mock_template = MagicMock(return_value=[HumanMessage(content="Mocked Prompt")])
    
    config = {"configurable": {"thread_id": "test"}}

    # Mock the internal metrics logger too
    mock_metrics = MagicMock()

    with patch("src.graph.nodes.reporter.get_llm_by_type", return_value=mock_llm), \
         patch("src.graph.nodes.reporter.apply_prompt_template", mock_template), \
         patch("src.utils.vli_metrics.log_vli_metric", mock_metrics):
        
        # 3. Execute the reporter node
        result = await reporter_node(state, config)
        
        # 4. Inspect what was passed to the prompt template
        args, _ = mock_template.call_args
        # args[1] is the state passed to apply_prompt_template
        compacted_state = args[1]
        messages = compacted_state["messages"]
        
        print(f"Number of compacted messages: {len(messages)}")
        
        # Verify the second message (the AIMessage) now has content describing the tool call
        ai_msg = messages[1]
        print(f"Repacked AIMessage content: {repr(ai_msg.content)}")
        
        if "[Agent invoked tool(s): run_smc_analysis]" in ai_msg.content:
            print("[SUCCESS] Tool-call description successfully injected into empty AIMessage.")
        else:
            print(f"[FAILURE] Injected content was: {repr(ai_msg.content)}")
            return False

        # Verify the sequence is Human -> AI -> Human (because ToolMessage was converted to HumanMessage)
        # Sequence: [HumanMessage, AIMessage (repacked), HumanMessage (Tool-returned)]
        types = [type(m).__name__ for m in messages]
        print(f"Message sequence types: {types}")
        if types == ["HumanMessage", "AIMessage", "HumanMessage"]:
            print("[SUCCESS] Message sequence is valid and alternating.")
        else:
            print(f"[FAILURE] Invalid message sequence: {types}")
            return False

        return True

async def main():
    # Run test twice as requested
    for i in range(2):
        print(f"\n=== TEST RUN {i+1} ===")
        success = await test_reporter_compaction_logic()
        if not success:
            sys.exit(1)
    
    print("\n>>> ALL TESTS PASSED: Fix verified via structural mocking.")

if __name__ == "__main__":
    asyncio.run(main())

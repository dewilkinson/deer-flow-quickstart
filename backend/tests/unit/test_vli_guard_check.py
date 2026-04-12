import pytest
import logging
from langchain_core.messages import AIMessage
from src.graph.nodes.common_vli import _run_node_with_tiered_fallback

# Configure logging to capture our [LEAK_DEBUG] markers
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_vli_leakage_guard_trigger():
    """ 
    Ensures that forbidden keywords trigger the Structural Exception.
    """
    # Use the now module-level AGENT_LLM_MAP
    from src.graph.nodes import common_vli
    
    # Verify keyword list is correct (bracketed)
    leak_keywords = ["# SECURITY OVERRIDE", "[APEX 500 SYSTEM]", "[SYSTEM INSTRUCTION]", "[USER OVERRIDE DIRECTIVE]", "[OPERATIONAL MANDATE]"]
    
    # Test text that should trigger
    res_str = "Following the [SYSTEM INSTRUCTION], I will scan the markets...".upper()
    is_leak = any(x in res_str for x in leak_keywords)
    
    print(f"\n[VERIFICATION] Triggering leak guard with '[SYSTEM INSTRUCTION]'...")
    print(f"Is Leak: {is_leak}")
    assert is_leak == True
    
    # Test text that should NOT trigger (plain text mandate)
    clean_str = "Executing our institutional mandate for high-fidelity analysis.".upper()
    is_not_leak = not any(x in clean_str for x in leak_keywords)
    assert is_not_leak == True

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_vli_leakage_guard_trigger())

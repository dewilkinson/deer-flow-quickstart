import os
import sys

# Ensure backend/src is in path if not already
sys.path.append(os.path.join(os.getcwd(), "backend"))


def test_node_isolation_standards():
    """Verify that all nodes in src/graph/nodes/ follow the 3-tier isolation standard."""
    import src.graph.nodes as nodes
    from src.tools.shared_storage import GLOBAL_CONTEXT

    # List of nodes to check
    node_files = [
        "analyst_node",
        "journaler_node",
        "coder_node",
        "coordinator_node",
        "parser_node",
        "reporter_node",
        "imaging_node",
        "human_feedback_node",
        "synthesizer_node",
        "vli_node",
        "smc_analyst_node",
    ]

    for node_name in node_files:
        node_module = getattr(nodes, node_name).__module__
        module = sys.modules[node_module]

        # 1. Private context exists and is truly local
        assert hasattr(module, "_NODE_RESOURCE_CONTEXT"), f"{node_name} missing _NODE_RESOURCE_CONTEXT"
        assert isinstance(module._NODE_RESOURCE_CONTEXT, dict)

        # 2. Shared context exists
        assert hasattr(module, "_SHARED_RESOURCE_CONTEXT"), f"{node_name} missing _SHARED_RESOURCE_CONTEXT"

        # 3. Global context exists and matches shared_storage.GLOBAL_CONTEXT
        assert hasattr(module, "_GLOBAL_RESOURCE_CONTEXT"), f"{node_name} missing _GLOBAL_RESOURCE_CONTEXT"
        assert module._GLOBAL_RESOURCE_CONTEXT is GLOBAL_CONTEXT


def test_tool_isolation_standards():
    """Verify that key tools follow the 3-tier isolation standard."""
    from src.tools.finance import _NODE_RESOURCE_CONTEXT as fin_tool_ctx
    from src.tools.research import _NODE_RESOURCE_CONTEXT as res_tool_ctx
    from src.tools.shared_storage import GLOBAL_CONTEXT
    from src.tools.smc import _NODE_RESOURCE_CONTEXT as smc_tool_ctx

    # Verify they are different objects (private isolation)
    assert res_tool_ctx is not fin_tool_ctx
    assert res_tool_ctx is not smc_tool_ctx
    assert fin_tool_ctx is not smc_tool_ctx

    # Verify global link
    import src.tools.finance as fin_mod
    import src.tools.research as res_mod
    import src.tools.smc as smc_mod

    assert res_mod._GLOBAL_RESOURCE_CONTEXT is GLOBAL_CONTEXT
    assert fin_mod._GLOBAL_RESOURCE_CONTEXT is GLOBAL_CONTEXT
    assert smc_mod._GLOBAL_RESOURCE_CONTEXT is GLOBAL_CONTEXT


def test_context_privacy_leakage():
    """Verify that modifying one private context does not affect others."""
    from src.graph.nodes.analyst import _NODE_RESOURCE_CONTEXT as ana_ctx
    from src.graph.nodes.vli import _NODE_RESOURCE_CONTEXT as vli_ctx

    vli_ctx["internal_secret"] = "vli_value"
    assert "internal_secret" not in ana_ctx

    ana_ctx["internal_secret"] = "ana_value"
    assert vli_ctx["internal_secret"] == "vli_value"
    assert ana_ctx["internal_secret"] == "ana_value"


def test_journaler_rebranding():
    """Verify that we used 'journaler' instead of 'journalist' everywhere."""
    from src.config.agents import AGENT_LLM_MAP

    assert "journaler" in AGENT_LLM_MAP
    assert "journalist" not in AGENT_LLM_MAP

    from src.graph.nodes import journaler_node

    assert journaler_node is not None


def test_graph_integrity():
    """Verify the multi-agent graph builds correctly."""
    from src.graph.builder import build_graph

    graph = build_graph()
    assert graph is not None
    # Check for expected nodes in the graph
    node_names = [n for n in graph.nodes]
    assert "vli" in node_names
    assert "analyst" in node_names
    assert "journaler" in node_names
    assert "reporter" in node_names
    assert "synthesizer" in node_names

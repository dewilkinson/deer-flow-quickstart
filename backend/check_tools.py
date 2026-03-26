
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.resolve()))

from src.tools import get_sortino_ratio
print(f"Tool name: {get_sortino_ratio.name}")

from src.agents.registry import registry
analyst_config = registry.get_agent_config("analyst")
print(f"Analyst tools: {analyst_config['tools']}")

if "get_sortino_ratio" in analyst_config["tools"]:
    print("MATCH: get_sortino_ratio is registered for Analyst.")
else:
    print("MISSING: get_sortino_ratio is NOT in analyst.json")

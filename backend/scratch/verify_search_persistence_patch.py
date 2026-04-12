import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.resolve()
sys.path.append(str(backend_path))
sys.path.append(str(backend_path / "src"))

import logging
logging.basicConfig(level=logging.INFO)

from src.tools.search import get_web_search_tool
from src.config.database import get_db, ResearchDocument
from unittest.mock import MagicMock, patch

def verify_persistence():
    print("=== Search Tool Persistence Verification (Patching Refactor) ===")
    
    # 1. Get the tool (Tavily is default in test mode)
    tool = get_web_search_tool(max_search_results=1)
    print(f"Tool Name: {tool.name}")
    print(f"Tool Type: {type(tool)}")
    
    # 2. Mock the actual search to avoid API calls
    mock_result = "Sample search result content for verification."
    
    # We need to find where _original_run was stored or just mock _run
    # Since we patched _run, we can mock the original one if we want, 
    # but it's easier to just mock the LLM-visible run method.
    
    # Actually, the tool we got is already patched.
    # To test persistence, we just need to CALL it.
    
    # We need to mock _original_run so it doesn't try to call the real API
    tool._original_run = MagicMock(return_value=mock_result)
    
    print("\nCalling patched _run...")
    result = tool._run("AAPL news")
    print(f"Result: {result}")

    # 3. Check DB
    print("\nChecking Database for persisted document...")
    db = next(get_db())
    doc = db.query(ResearchDocument).filter(ResearchDocument.title.like("%AAPL%")).first()
    
    if doc:
        print(f"[SUCCESS] Found document: {doc.title}")
        print(f"Content: {doc.content[:50]}...")
        
        # Clean up
        db.delete(doc)
        db.commit()
        print("Cleanup complete.")
    else:
        print("[FAIL] Document not found in database.")

if __name__ == "__main__":
    verify_persistence()

# VLI Spine Entry Point for LangGraph Server
# This file provides a clean export with absolute imports to avoid the 'relative import' error.

import logging
from src.graph import build_graph

# Configure minimal logging for the server environment
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Compile the VLI Spine graph (clean compilation for LangGraph Server)
graph = build_graph()

# Set config defaults if needed
graph.config = {"recursion_limit": 100}

if __name__ == "__main__":
    # Test the graph export
    print("VLI Spine Graph loaded successfully.")

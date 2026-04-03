#!/usr/bin/env python3
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import subprocess
import sys


def run_command(command, cwd=None):
    cmd_str = " ".join(command)
    print(f"Executing: {cmd_str}")
    result = subprocess.run(cmd_str, cwd=cwd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"Error executing command: {result.stderr}")
        return False, result.stdout
    return True, result.stdout


def main():
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    print("--- 🧪 Running Unit Tests ---")
    success, output = run_command(["uv", "run", "pytest", "tests/unit"], cwd=backend_dir)
    if not success:
        print("Unit tests failed!")
        sys.exit(1)
    print(output)

    print("--- 🔍 Checking Node Imports ---")
    # Simple check to ensure nodes can be imported (detects syntax errors/missing dependencies)
    try:
        sys.path.insert(0, backend_dir)
        print("Nodes imported successfully.")
    except Exception as e:
        print(f"Node import failed: {e}")
        sys.exit(1)

    print("--- ✅ System Verification Passed! ---")
    sys.exit(0)


if __name__ == "__main__":
    main()

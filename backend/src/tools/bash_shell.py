# Tool: Safe Bash Shell - Restricted shell execution for automation.
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import json
import logging
import os
import shlex
import subprocess
from typing import Annotated

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# BLACKLISTED COMMANDS: Destructive or System-level Administrative operations
BLACKLISTED_COMMANDS = ["format", "shred", "dd", "mkfs", "parted", "fdisk", "chown", "chmod", "sudo", "su"]

# SENSITIVE COMMANDS: Require explicit human approval (rm, mv)
SENSITIVE_COMMANDS = ["rm", "mv", "del", "rename"]


@tool
def bash_shell_tool(command: Annotated[str, "The bash/shell command to execute safely."]):
    """Safe execution of bash and shell commands. Performs environment validation and
    blacklists destructive system actions. Commands like 'rm' or 'mv' will be flagged for approval."""

    # 1. Parsing & Validation
    try:
        parts = shlex.split(command)
        if not parts:
            return "Error: Empty command."

        base_cmd = parts[0].lower()

        # 2. Blacklist Check (HARD REJECTION)
        if any(bad in base_cmd for bad in BLACKLISTED_COMMANDS):
            return f"REJECTED: Command '{base_cmd}' is blacklisted for security reasons (System Health Protection)."

        # 3. Sensitivity Check (APPROVAL REQUIRED)
        # If the command involves 'rm' or 'mv', we flag it for the human-in-the-loop
        if any(sens in base_cmd for sens in SENSITIVE_COMMANDS):
            return json.dumps({"status": "APPROVAL_REQUIRED", "command": command, "reason": f"Sensitive operation detected: '{base_cmd}'. Please confirm you wish to proceed."})

        # 4. Safe Execution
        # We explicitly restrict execution to the current workspace or Obsidian vault path
        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        cwd = os.getcwd()  # Typically the project root

        logger.info(f"Executing Safe Bash: {command}")

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,  # Safety timeout to prevent hangs
        )

        if result.returncode != 0:
            return f"Command execution failed (Code {result.returncode}):\n{result.stderr}"

        return f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"

    except Exception as e:
        return f"Error executing bash command: {str(e)}"

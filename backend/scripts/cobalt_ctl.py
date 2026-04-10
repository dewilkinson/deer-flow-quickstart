import sys
import os
import json
import argparse
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

try:
    from src.utils.hardware import get_system_hardware, get_recommended_config
except ImportError:
    print("Error: Could not import hardware utils. Ensure you are running from the /backend directory.")
    sys.exit(1)

def print_hardware_report(hw, config):
    print("\n" + "="*50)
    print("COBALT HARDWARE COMPATIBILITY REPORT")
    print("="*50)
    
    print(f"\n[SYSTEM PROFILE]: {config['category']}")
    print("-" * 30)
    
    # Process CPU
    cpu = hw.get("cpus", [{}])[0]
    print(f"CPU: {cpu.get('Name', 'Unknown')}")
    print(f"     {cpu.get('NumberOfCores', 0)} Cores / {cpu.get('NumberOfLogicalProcessors', 0)} Logical")
    
    # Process RAM
    ram_gb = hw.get("ram_bytes", 0) / (1024**3)
    print(f"RAM: {ram_gb:.2f} GB")
    
    # Process GPU
    print("GPU(s):")
    for gpu in hw.get("gpus", []):
        vram_gb = (gpu.get("AdapterRAM", 0) or 0) / (1024**3)
        print(f"     - {gpu.get('Name', 'Unknown')} ({vram_gb:.2f} GB VRAM)")
    
    print("\n[RECOMMENDED CONFIGURATION]")
    print("-" * 30)
    print(f"CORE (Orchestrator): {config['core']['model']} ({config['core']['platform']})")
    print(f"                      Reason: {config['core']['reason']}")
    print(f"RESEARCH (Analysis):  {config['research']['model']} ({config['research']['platform']})")
    print(f"VISION (Charts):      {config['vision']['model']} ({config['vision']['platform']})")
    print("="*50 + "\n")

def update_env(config, dry_run=False):
    env_path = Path(".env")
    if not env_path.exists():
        print("Error: .env file not found.")
        return

    # Create backup
    if not dry_run:
        import shutil
        shutil.copy(".env", ".env.bak")
        print("Backup created: .env.bak")

    with open(env_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    updated_keys = set()
    
    # Mapping our config keys to .env prefixes
    mapping = {
        "core": "CORE_MODEL__",
        "research": "REASONING_MODEL__",
        "vision": "VISION_MODEL__"
    }

    for line in lines:
        stripped = line.strip()
        matched = False
        for cfg_key, prefix in mapping.items():
            if stripped.startswith(f"{prefix}model="):
                new_val = config[cfg_key]["model"]
                new_lines.append(f"{prefix}model={new_val}\n")
                updated_keys.add(f"{prefix}model")
                matched = True
                break
            elif stripped.startswith(f"{prefix}platform="):
                new_val = config[cfg_key]["platform"]
                new_lines.append(f"{prefix}platform={new_val}\n")
                updated_keys.add(f"{prefix}platform")
                matched = True
                break
        
        if not matched:
            new_lines.append(line)

    if dry_run:
        print("\n--- DRY RUN: Proposed .env Changes ---")
        for key in updated_keys:
            print(f"Plan to update {key}")
    else:
        with open(env_path, "w") as f:
            f.writelines(new_lines)
        print("SUCCESS: .env updated to optimum configuration.")

def main():
    parser = argparse.ArgumentParser(description="Cobalt Hardware Control Utility")
    parser.add_argument("command", choices=["hw-check", "optimum-config"], help="Command to run")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes to disk")
    
    args = parser.parse_args()
    
    hw = get_system_hardware()
    config = get_recommended_config(hw)
    
    if args.command == "hw-check":
        print_hardware_report(hw, config)
    elif args.command == "optimum-config":
        update_env(config, dry_run=args.dry_run)

if __name__ == "__main__":
    main()

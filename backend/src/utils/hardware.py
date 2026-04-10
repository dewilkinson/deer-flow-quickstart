import json
import subprocess
import logging

logger = logging.getLogger(__name__)


def get_system_hardware() -> dict:
    """
    Get system hardware information using native Windows PowerShell commands.
    Returns:
        A dictionary with 'cpu', 'gpu', and 'ram' information.
    """
    try:
        # 1. Get GPU Information
        gpu_cmd = "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"
        gpu_json = subprocess.check_output(["powershell", "-Command", gpu_cmd], text=True, stderr=subprocess.STDOUT)
        gpus = json.loads(gpu_json)
        if isinstance(gpus, dict):
            gpus = [gpus]

        # 2. Get CPU Information
        cpu_cmd = "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors | ConvertTo-Json"
        cpu_json = subprocess.check_output(["powershell", "-Command", cpu_cmd], text=True, stderr=subprocess.STDOUT)
        cpus = json.loads(cpu_json)
        if isinstance(cpus, dict):
            cpus = [cpus]

        # 3. Get RAM Information
        ram_cmd = "Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory | ConvertTo-Json"
        ram_json = subprocess.check_output(["powershell", "-Command", ram_cmd], text=True, stderr=subprocess.STDOUT)
        ram = json.loads(ram_json)

        return {"gpus": gpus, "cpus": cpus, "ram_bytes": ram.get("TotalPhysicalMemory", 0)}
    except Exception as e:
        logger.error(f"Failed to scan hardware: {e}")
        return {"error": str(e)}


def categorize_system(hw: dict) -> str:
    """
    Categorize the system based on hardware capabilities.
    Returns: 'Entry', 'Mid', 'High', or 'Ultra'
    """
    if "error" in hw:
        return "Unknown"

    vram_total = 0
    has_nvidia = False

    for gpu in hw.get("gpus", []):
        name = gpu.get("Name", "").lower()
        if "nvidia" in name:
            has_nvidia = True
        vram = gpu.get("AdapterRAM", 0)
        if vram:
            vram_total += int(vram)

    ram_gb = hw.get("ram_bytes", 0) / (1024**3)

    if has_nvidia and vram_total >= 16 * (1024**3):
        return "High"
    elif has_nvidia and vram_total >= 8 * (1024**3):
        return "Mid"
    elif ram_gb >= 32:
        return "Mid"  # High memory CPU inference
    else:
        return "Entry"


def get_recommended_config(hw: dict) -> dict:
    """
    Generate recommended model configuration based on hardware category.
    """
    category = categorize_system(hw)

    config = {
        "category": category,
        "core": {"platform": "google_aistudio", "model": "gemma-4-31b-it", "reason": "Stable high-fidelity cloud reasoning."},
        "research": {"platform": "google_aistudio", "model": "gemini-3-flash-preview", "reason": "Fast analysis path enabled by default."},
        "vision": {"platform": "google_aistudio", "model": "gemini-2.0-flash", "reason": "High-fidelity cloud OCR benchmark."},
    }

    if category == "Entry":
        # Low hardware: Recommend E4B for local core, keep others cloud
        config["core"] = {"platform": "ollama", "model": "gemma4:e4b", "reason": "Optimized 4B variant for CPU-bound local execution."}
    elif category in ["Mid", "High"]:
        # Better hardware: Can run 31B/26B locally or keep cloud 31B
        config["core"] = {"platform": "ollama", "model": "gemma4:31b", "reason": "Local 31B Dense model for high-fidelity private reasoning."}

    return config

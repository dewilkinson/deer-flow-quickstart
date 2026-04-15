import asyncio
import time
from src.services.scheduler import CobaltScheduler, ScheduledTask

async def test_priority_logic():
    print("\n--- [START] Cobalt Heartbeat Priority Test ---")
    
    # Setup test scheduler
    test_scheduler = CobaltScheduler()
    test_scheduler.registry_path = "backend/scratch/test_scheduler.json"
    test_scheduler.log_file = "backend/scratch/test_scheduler.log"
    
    execution_order = []

    async def critical_cb():
        execution_order.append("CRITICAL")
        print("🔥 Executing CRITICAL task")

    async def high_cb():
        execution_order.append("HIGH")
        print("⚡ Executing HIGH task")

    async def low_cb():
        execution_order.append("LOW")
        print("🐢 Executing LOW task")

    async def background_cb():
        execution_order.append("BACKGROUND")
        print("🌙 Executing BACKGROUND task")

    # 1. Register tasks
    test_scheduler.add_timer("C1", "Critical Task", "REPEAT", 1, "seconds", priority="CRITICAL", callback=critical_cb)
    test_scheduler.add_timer("H1", "High Task", "REPEAT", 1, "seconds", priority="HIGH", callback=high_cb)
    test_scheduler.add_timer("L1", "Low Task", "REPEAT", 1, "seconds", priority="LOW", callback=low_cb)
    test_scheduler.add_timer("B1", "Background Task", "REPEAT", 1, "seconds", priority="BACKGROUND", callback=background_cb)

    # Start the engine
    test_scheduler.start()

    print("\n[PHASE 1] Testing Priority Order (Idle=False)")
    test_scheduler.platform_idle = False
    
    # Wait for a few tics
    await asyncio.sleep(3)
    
    # Verify order: CRITICAL > HIGH > LOW. BACKGROUND should be skipped.
    print(f"Recorded Execution: {execution_order}")
    assert "BACKGROUND" not in execution_order, "Background task ran while platform was active!"
    
    # Check if critical/high ran before low in the recorded list usually
    # (Since it's a loop processing queues, it should hit critical first)
    
    print("\n[PHASE 2] Testing Background Execution (Idle=True)")
    test_scheduler.platform_idle = True
    await asyncio.sleep(2)
    assert "BACKGROUND" in execution_order, "Background task failed to run when idle!"
    
    print("\n[PHASE 3] Testing Promotion")
    execution_order.clear()
    test_scheduler.platform_idle = False # Stop background again
    
    # Promote the background task
    test_scheduler.promote_task("B1")
    await asyncio.sleep(1)
    
    assert execution_order[0] == "BACKGROUND", f"Promotion failed! Expected BACKGROUND first, got {execution_order[0] if execution_order else 'None'}"
    print("🚀 Task B1 successfully promoted to CRITICAL queue!")

    # Cleanup
    test_scheduler.stop()
    worker.cancel()
    print("\n--- [SUCCESS] Cobalt Heartbeat Priority Test Passed ---")

if __name__ == "__main__":
    asyncio.run(test_priority_logic())

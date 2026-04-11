import asyncio
import httpx
import time

async def main():
    print("Starting concurrent backend verification test...")
    # Simulate the frontend's fetch('/api/vli/action-plan') for NVDA
    async with httpx.AsyncClient() as client:
        print("[Client 1] Submitting 'Analyze NVDA' directive...")
        task = asyncio.create_task(
            client.post('http://127.0.0.1:5000/api/vli/action-plan', json={'text': 'analyze NVDA'}, timeout=120)
        )
        
        # Simulate an impatient subagent (or user) pressing Enter again which triggers stopMessage() -> fetch('/api/vli/reset')
        await asyncio.sleep(2)
        print("\n[Client 2] Simulating double-Enter/Restart press causing fetch('/api/vli/reset')...")
        reset_res = await client.post('http://127.0.0.1:5000/api/vli/reset', timeout=10)
        print(f"[Client 2] Reset Response: {reset_res.json()}")
        
        # Now wait for the first task to see what happens
        try:
            print("\n[Client 1] Awaiting original NVDA query response...")
            res = await task
            print(f"[Client 1] Received status: {res.status_code}")
            # The backend will terminate the background task. Depending on FastAPI behavior, it might return 500 or timeout string.
            print(f"[Client 1] Body: {res.text[:200]}")
        except Exception as e:
            print(f"[Client 1] Exception caught: {e}")

if __name__ == "__main__":
    asyncio.run(main())

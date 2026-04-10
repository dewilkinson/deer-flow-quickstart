import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://127.0.0.1:8000/api/vli/action-plan', json={'text':'Analyze AAPL'}, timeout=120)
        print(r.json())

if __name__ == "__main__":
    asyncio.run(main())

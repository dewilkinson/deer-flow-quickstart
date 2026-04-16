import asyncio
from src.tools.finance import get_macro_symbols
async def test():
    res = await get_macro_symbols.func(fast_update=False)
    import json
    data = json.loads(res)['rows']
    for r in data:
        print(r[0], r[1])
        if r[1] == 'NQ=F':
            print(r[5]['value'])
asyncio.run(test())

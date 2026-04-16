import asyncio, sys, os, json
sys.path.append(os.path.abspath('backend'))
from src.tools.finance import get_macro_symbols, _fetch_direct_sparkline, _extract_ticker_data

async def main():
    data_5m = await _fetch_direct_sparkline(['GC=F'])
    for col in data_5m.columns:
        print(col)
    
    # Actually just print the head of GC_F
    print("GC=F HEAD:")
    print(data_5m.head(5))

    # Print the very first valid row for Close
    print("GC=F Close head:")
    col = "Close" if "Close" in data_5m.columns else "close"
    if col in data_5m.columns:
        print(data_5m[col].dropna().head(5))
    else:
        # MultiIndex accessing
        df_gc = _extract_ticker_data(data_5m, 'GC=F')
        print(df_gc['Close'].head(5))

if __name__ == '__main__':
    asyncio.run(main())

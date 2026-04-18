import yfinance
import json

def check_yf():
    print("Checking yfinance for AAPL...")
    t = yfinance.Ticker('AAPL')
    fast = t.fast_info
    print(f"Type: {type(fast)}")
    
    # Try common attributes
    results = {
        "last_price": getattr(fast, "last_price", "N/A"),
        "previous_close": getattr(fast, "previous_close", "N/A"),
        "last_volume": getattr(fast, "last_volume", "N/A"),
        "currency": getattr(fast, "currency", "N/A")
    }
    print(f"Attributes: {results}")
    
    # Check if it's iterable or dict-like
    try:
        print(f"Keys (if dict-like): {list(fast.keys())}")
    except:
        print("Not dict-like (no .keys())")

if __name__ == "__main__":
    check_yf()

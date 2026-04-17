import re

def test_fast_path(text):
    cleaned_input = text.strip().upper()
    ticker = None
    fp_intent = None
    
    m1 = re.match(r"^(?:GET\s+)?\$?([A-Z]{1,5})(?:\s+PRICE)?$", cleaned_input)
    m2 = re.match(r"^PRICE\s+OF\s+\$?([A-Z]{1,5})$", cleaned_input)
    
    if m1:
        ticker = m1.group(1)
        fp_intent = "Shorthand/Price"
    elif m2:
        ticker = m2.group(1)
        fp_intent = "Price of Ticker"
    
    return ticker, fp_intent

tests = [
    "AAPL",
    "$NVDA",
    "get aapl",
    "get $msft",
    "get aapl price",
    "get $nvda price",
    "price of googl",
    "price of $tsla",
    "meta price",
    "$meta price",
    "analyze aapl", # Should NOT match
    "what is the price of aapl", # Should NOT match (Fast Path is for shorthand)
]

for t in tests:
    ticker, intent = test_fast_path(t)
    print(f"'{t}' -> Ticker: {ticker}, Intent: {intent}")

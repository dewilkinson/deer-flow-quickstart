# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import yfinance as yf
from langchain_core.tools import tool
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

@tool
def get_stock_quote(ticker: str) -> Union[Dict[str, Any], str]:
    """
    Get current stock quote and OHLC (Open, High, Low, Close) data for a given ticker symbol.
    
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'NVDA', 'TSLA').
        
    Returns:
        A dictionary containing symbol, price, open, high, low, close, and volume, 
        or an error message if the ticker is invalid.
    """
    logger.info(f"Fetching stock quote for {ticker}")
    try:
        stock = yf.Ticker(ticker)
        # Detail the connection/request info
        connection_info = f"Requesting '{ticker}' from Yahoo Finance API (yfinance v2)..."
        params = {"ticker": ticker, "period": "5d", "interval": "1d"}
        
        data = stock.history(period="5d")
        
        if data.empty:
            return f"[ERROR]: No data found for ticker '{ticker}'.\n[CONN_INFO]: {connection_info}"
        
        last_row = data.iloc[-1]
        raw_payload = data.tail(1).to_json(orient="records")
        
        report = f"""
[TECHNICAL_LOG]
Status: SUCCESS
Connection: {connection_info}
Parameters: {params}

[API_PAYLOAD]
{raw_payload}

[OHLC_DATA]
Symbol: {ticker.upper()}
Currency: {stock.info.get("currency", "USD")}
Date: {last_row.name.strftime('%Y-%m-%d')}
Open: {round(float(last_row['Open']), 2)}
High: {round(float(last_row['High']), 2)}
Low: {round(float(last_row['Low']), 2)}
Close: {round(float(last_row['Close']), 2)}
Current: {round(float(last_row['Close']), 2)}
Volume: {int(last_row['Volume'])}
"""
        return report.strip()
    except Exception as e:
        logger.error(f"Error in get_stock_quote for {ticker}: {str(e)}")
        return f"[ERROR]: {str(e)}\n[CONN_INFO]: Attempted connection to Yahoo Finance for {ticker}"


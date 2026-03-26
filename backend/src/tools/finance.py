# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Core financial primitives and data retrieval.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
import asyncio
import yfinance as yf
import pandas as pd
from langchain_core.tools import tool
from typing import Dict, Any, Union, List

logger = logging.getLogger(__name__)

from .shared_storage import SCOUT_CONTEXT, GLOBAL_CONTEXT

# 1. Private context: Truly private to this module instance.
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by all agents of the SAME type.
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


def _fetch_stock_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """Internal helper to fetch OHLC data as a DataFrame using yfinance (Scout Restricted)."""
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    return df




def _fetch_symbol_history_data(symbol: str, p: str, i: str):
    """Internal helper to fetch history for a single symbol."""
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period=p, interval=i)
        if data.empty:
            return f"### {symbol}\n- [ERROR]: No data found.\n"
        
        last_row = data.iloc[-1]
        try:
            currency = stock.fast_info.get("currency", "USD") if hasattr(stock, "fast_info") else "USD"
        except Exception:
            currency = "USD"
        
        return f"""
### {symbol.upper()} ({currency})
- **Period**: {p} | **Interval**: {i}
- **Close**: {float(last_row['Close']):.2f}
- **High**: {float(last_row['High']):.2f}
- **Low**: {float(last_row['Low']):.2f}
- **Volume**: {int(last_row['Volume']):,}
"""
    except Exception as e:
        return f"### {symbol}\n- [ERROR]: {str(e)}\n"

@tool
async def get_symbol_history_data(symbols: List[str], period: str = "1d", interval: str = "1h") -> str:
    """
    Scout Primitive: Retrieve stock history for multiple symbols and return a structured markdown report.
    
    Args:
        symbols: A list of stock ticker symbols (e.g., ['AAPL', 'NVDA', 'TSLA']).
        period: The lookback period (default '1d').
        interval: The timeframe interval (default '1h').
        
    Returns:
        A markdown-formatted string containing the history for all requested symbols.
    """
    logger.info(f"Scout fetching history for {len(symbols)} symbols (p={period}, i={interval})")
    
    # Check cache first
    history_cache = _NODE_RESOURCE_CONTEXT.setdefault("history_cache", {})
    cache_key = f"{','.join(sorted(symbols))}_{period}_{interval}"
    if cache_key in history_cache:
        logger.info("Using cached symbol history data.")
        return history_cache[cache_key]
    
    try:
        tasks = [asyncio.to_thread(_fetch_symbol_history_data, sym, period, interval) for sym in symbols]
        results = await asyncio.gather(*tasks)
        
        report = f"# Stock History Report\nGenerated at {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', {}, None))}\n\n"
        report += "\n".join(results)
        
        # Save to cache if no errors occurred
        if "[ERROR]" not in report:
            history_cache[cache_key] = report.strip()
            
        return report.strip()
    except Exception as e:
        logger.error(f"Error in get_symbol_history_data: {str(e)}")
        return f"[ERROR]: Failed to fetch history list: {str(e)}"



@tool
async def get_stock_quote(ticker: str, period: str = "5d", interval: str = "1d") -> Union[Dict[str, Any], str]:
    """
    Get current stock quote and OHLC (Open, High, Low, Close) data for a given ticker symbol.
    
    Args:
        ticker: The stock ticker symbol (e.g., 'AAPL', 'NVDA', 'TSLA').
        period: The lookback period (e.g., '1d', '5d', '1mo', '1y').
        interval: The timeframe interval (e.g., '1m', '5m', '15m', '1h', '1d').
        
    Returns:
        A dictionary containing symbol, price, open, high, low, close, and volume, 
        or an error message if the ticker is invalid.
    """
    logger.info(f"Fetching stock quote for {ticker} (p={period}, i={interval})")
    
    # Inner synchronous fetching function to be run in a separate thread
    def fetch_data(ticker_symbol: str, p: str, i: str):
        logger.info(f"Initializing ticker in thread for '{ticker_symbol}'...")
        stock = yf.Ticker(ticker_symbol)
        connection_info = f"Requesting '{ticker_symbol}' from Yahoo Finance API (yfinance v2)..."
        params = {"ticker": ticker_symbol, "period": p, "interval": i}
        
        logger.info(f"Fetching history in thread (p={p}, i={i})...")
        data = stock.history(period=p, interval=i)
        
        logger.info("History fetched in thread.")
        if data.empty:
            return f"[ERROR]: No data found for ticker '{ticker_symbol}'.\n[CONN_INFO]: {connection_info}\n[PARAMS]: {params}"
        
        last_row = data.iloc[-1]
        raw_payload = data.tail(1).to_json(orient="records")
        
        logger.info("Fetching currency...")
        try:
            # Avoid notoriously slow stock.info which can hang indefinitely.
            currency = stock.fast_info.get("currency", "USD") if hasattr(stock, "fast_info") else "USD"
        except Exception:
            currency = "USD"
        logger.info(f"Currency fetched: {currency}")
        
        report = f"""
[TECHNICAL_LOG]
Status: SUCCESS
Connection: {connection_info}
Parameters: {params}

[API_PAYLOAD]
{raw_payload}

[OHLC_DATA]
Symbol: {ticker_symbol.upper()}
Currency: {currency}
Date: {last_row.name.strftime('%Y-%m-%d %H:%M:%S') if hasattr(last_row.name, 'strftime') else last_row.name}
Open: {float(last_row['Open']):.2f}
High: {float(last_row['High']):.2f}
Low: {float(last_row['Low']):.2f}
Close: {float(last_row['Close']):.2f}
Current: {float(last_row['Close']):.2f}
Volume: {int(last_row['Volume'])}
"""
        return report.strip()

    try:
        # Implementing a 15-second timeout for the synchronous yfinance data fetching
        result = await asyncio.wait_for(asyncio.to_thread(fetch_data, ticker, period, interval), timeout=15.0)
        return result
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching stock quote for {ticker} after 15 seconds")
        return f"[ERROR]: Timeout (15s) while attempting to fetch '{ticker}' from Yahoo Finance API."
    except Exception as e:
        logger.error(f"Error in get_stock_quote for {ticker}: {str(e)}")
        return f"[ERROR]: {str(e)}\n[CONN_INFO]: Attempted connection to Yahoo Finance for {ticker}"


@tool
async def get_sharpe_ratio(ticker: str, period: str = "1y") -> str:
    """
    Scout Primitive: Calculate the Sharpe Ratio for a given ticker.
    Uses the 10Y Treasury Yield (^TNX) as the risk-free rate proxy.
    
    Args:
        ticker: The stock ticker symbol.
        period: The lookback period (default '1y').
    """
    try:
        df = await asyncio.to_thread(_fetch_stock_history, ticker, period, "1d")
        if df.empty:
            return f"### Sharpe Ratio: {ticker.upper()}\n[ERROR]: No data found for specified period."
        
        # Risk-free rate proxy from ^TNX
        tnx = yf.Ticker("^TNX")
        try:
            rf_rate = tnx.fast_info.get("lastPrice", 4.3) / 100.0
        except Exception:
            rf_rate = 0.043 # Fallback to 4.3%
            
        returns = df['Close'].pct_change().dropna()
        excess_returns = returns - (rf_rate / 252)
        sharpe = (excess_returns.mean() / excess_returns.std()) * (252**0.5)
        
        return f"### Sharpe Ratio: {ticker.upper()}\n- **Value:** {sharpe:.2f}\n- **Risk-Free Rate (Proxy ^TNX):** {rf_rate*100:.2f}%\n"
    except Exception as e:
        logger.error(f"Error calculating Sharpe for {ticker}: {str(e)}")
        return f"### Sharpe Ratio: {ticker.upper()}\n[ERROR]: {str(e)}"


@tool
async def get_sortino_ratio(ticker: str, period: str = "1y") -> str:
    """
    Scout Primitive: Calculate the Sortino Ratio (downside risk-adjusted return) for a given ticker.
    Uses the 10Y Treasury Yield (^TNX) as the risk-free rate proxy.
    
    Args:
        ticker: The stock ticker symbol.
        period: The lookback period (default '1y').
    """
    try:
        df = await asyncio.to_thread(_fetch_stock_history, ticker, period, "1d")
        if df.empty:
            return f"### Sortino Ratio: {ticker.upper()}\n[ERROR]: No data found for specified period."
        
        tnx = yf.Ticker("^TNX")
        try:
            rf_rate = tnx.fast_info.get("lastPrice", 4.3) / 100.0
        except Exception:
            rf_rate = 0.043
            
        returns = df['Close'].pct_change().dropna()
        excess_returns = returns - (rf_rate / 252)
        
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = downside_returns.std() * (252**0.5)
        
        sortino = (excess_returns.mean() * 252) / downside_std if downside_std != 0 else 0
        
        return f"### Sortino Ratio: {ticker.upper()}\n- **Value:** {sortino:.2f}\n- **Risk-Free Rate (Proxy ^TNX):** {rf_rate*100:.2f}%\n"
    except Exception as e:
        logger.error(f"Error calculating Sortino for {ticker}: {str(e)}")
        return f"### Sortino Ratio: {ticker.upper()}\n[ERROR]: {str(e)}"


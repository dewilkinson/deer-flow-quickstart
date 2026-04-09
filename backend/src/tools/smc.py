# Agent: Analyst - Smart Money Concepts and advanced structure analysis.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import logging
from typing import Any

import pandas as pd
from langchain_core.tools import tool

from .finance import _fetch_stock_history

logger = logging.getLogger(__name__)

from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context: Persistent, shared by Analyst sub-modules
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


def detect_fvg(df: pd.DataFrame):
    """Detects Fair Value Gaps (FVG)."""
    fvgs = []
    # Needs at least 3 candles to find a gap
    for i in range(2, len(df)):
        # Bullish FVG
        if df["high"].iloc[i - 2] < df["low"].iloc[i]:
            fvgs.append({"type": "Bullish", "top": df["low"].iloc[i], "bottom": df["high"].iloc[i - 2], "date": df.index[i].strftime("%Y-%m-%d")})
        # Bearish FVG
        elif df["low"].iloc[i - 2] > df["high"].iloc[i]:
            fvgs.append({"type": "Bearish", "top": df["low"].iloc[i - 2], "bottom": df["high"].iloc[i], "date": df.index[i].strftime("%Y-%m-%d")})
    return fvgs


def detect_structure(df: pd.DataFrame):
    """Simple BOS detection."""
    # Find local swing highs/lows
    # Simplification: Use rolling window to find relative peaks
    window = 10
    df["peak_high"] = df["high"].rolling(window=window, center=True).max()
    df["peak_low"] = df["low"].rolling(window=window, center=True).min()

    breaks = []
    current_trend = None

    for i in range(window, len(df)):
        # Check for break of historical peak high
        past_peak_high = df["peak_high"].iloc[i - window : i].max()
        if df["close"].iloc[i] > past_peak_high:
            if current_trend != "Bullish":
                breaks.append({"type": "BOS (Bullish)", "date": df.index[i].strftime("%Y-%m-%d")})
                current_trend = "Bullish"

        # Check for break of historical peak low
        past_peak_low = df["peak_low"].iloc[i - window : i].min()
        if df["close"].iloc[i] < past_peak_low:
            if current_trend != "Bearish":
                breaks.append({"type": "BOS (Bearish)", "date": df.index[i].strftime("%Y-%m-%d")})
                current_trend = "Bearish"

    return breaks


@tool
async def get_smc_analysis(ticker: str, period: str = "60d", interval: str = "1d") -> str:
    """
    Perform Smart Money Concepts (SMC) technical analysis on a given ticker.
    Detects Fair Value Gaps (FVG) and Market Structure (BOS).
    Best for finding high-probability reversal and continuation zones.

    Args:
        ticker: The stock ticker symbol.
        period: The lookback period (e.g., '60d', '1mo', '1y').
        interval: The timeframe interval (e.g., '1h', '1d', '1wk').
    """

    def compute_smc(symbol: str, p: str, i: str):
        logger.info(f"Computing SMC using smartmoneyconcepts library for {symbol}")
        try:
            from smartmoneyconcepts import smc
        except ImportError:
            return "[ERROR]: The 'smartmoneyconcepts' library is required."
            
        df = _fetch_stock_history(symbol, p, i)

        if df.empty:
            return f"Error: No data found for ticker '{symbol}' with period '{p}' and interval '{i}'."

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]

        # SMC requires lowercase OHLCV
        df.columns = [str(c).lower() for c in df.columns]

        # Compute all SMC data points
        swings = smc.swing_highs_lows(df, swing_length=5)
        structure = smc.bos_choch(df, swings)
        ob = smc.ob(df, swings)
        fvg = smc.fvg(df)
        liq = smc.liquidity(df, swings)

        # Concatenate outputs with the original dataframe (resetting index to guarantee row alignment)
        combined_df = pd.concat([
            df.reset_index(drop=True), 
            swings.reset_index(drop=True), 
            structure.reset_index(drop=True), 
            ob.reset_index(drop=True), 
            fvg.reset_index(drop=True), 
            liq.reset_index(drop=True)
        ], axis=1)
        
        # Deduplicate identical column names caused by merging different SMC indicator outputs
        combined_df = combined_df.loc[:, ~combined_df.columns.duplicated(keep='last')]
        
        # Drop columns that are completely NA across all rows to save space
        combined_df.dropna(axis=1, how='all', inplace=True)

        # Keep only the rows where a structural event occurred (to prevent the LLM from getting lost in nulls)
        event_columns = [col for col in ['BOS', 'bos', 'CHOCH', 'choch', 'OB', 'ob', 'FVG', 'fvg', 'Liquidity', 'liquidity', 'Level'] if col in combined_df.columns]
        
        # Rows with any event
        if event_columns:
            events_mask = combined_df[event_columns].notna().any(axis=1)
        else:
            events_mask = pd.Series(False, index=combined_df.index)
            
        # Plus the last 5 candles unconditionally for context
        recent_mask = combined_df.index >= len(combined_df) - 5
        
        final_df = combined_df[events_mask | recent_mask]

        # Return compressed payload as JSON string
        return final_df.to_json(orient="records", date_format="iso")

    try:
        return await asyncio.wait_for(asyncio.to_thread(compute_smc, ticker, period, interval), timeout=25.0)
    except Exception as e:
        logger.error(f"Custom SMC Tool error: {str(e)}")
        return f"Error during SMC analysis: {str(e)}"

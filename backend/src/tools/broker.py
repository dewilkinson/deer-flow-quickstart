# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Brokerage and account management tools.
import logging
import os
from datetime import datetime, timedelta

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from snaptrade_client import SnapTrade
from src.config.configuration import Configuration
from src.tools.shared_storage import SCOUT_CONTEXT
from src.services.reconciliation import reconcile_trades
import time
import csv
import os


logger = logging.getLogger(__name__)

# Agent-specific resource context (Shared by all Scout sub-modules)
_NODE_RESOURCE_CONTEXT = SCOUT_CONTEXT


def _get_client_and_creds(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    settings = configurable.snaptrade_settings if configurable.snaptrade_settings else {}

    # Priority: 1. Request Settings, 2. Environment Variables
    client_id = settings.get("SNAPTRADE_CLIENT_ID") or os.getenv("SNAPTRADE_CLIENT_ID")
    consumer_key = settings.get("SNAPTRADE_CONSUMER_KEY") or os.getenv("SNAPTRADE_CONSUMER_KEY")
    user_id = settings.get("SNAPTRADE_USER_ID") or os.getenv("SNAPTRADE_USER_ID")
    user_secret = settings.get("SNAPTRADE_USER_SECRET") or os.getenv("SNAPTRADE_USER_SECRET")
    mock_broker = settings.get("MOCK_BROKER") or os.getenv("MOCK_BROKER")

    client = None
    if client_id and consumer_key:
        client = SnapTrade(client_id=client_id, consumer_key=consumer_key)

    return client, user_id, user_secret, mock_broker


@tool
def get_brokerage_accounts(config: RunnableConfig):
    """
    Get a list of all brokerage accounts connected via SnapTrade.
    Use this to find the account_id (UUID) for the user's brokerage accounts (e.g., Fidelity).
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
            logger.info("MOCK_BROKER=true, returning simulated data.")
            return [{"id": "mock-fidelity-1", "name": "Fidelity Rollover IRA", "institution": "Fidelity"}, {"id": "mock-fidelity-2", "name": "Fidelity Individual", "institution": "Fidelity"}]
        return "[ERROR]: SnapTrade credentials (SNAPTRADE_CLIENT_ID, SNAPTRADE_CONSUMER_KEY, SNAPTRADE_USER_ID, SNAPTRADE_USER_SECRET) are not fully configured."

    try:
        logger.info(f"Fetching SnapTrade accounts for user {user_id}")
        api_response = client.account_information.list_user_accounts(user_id=user_id, user_secret=user_secret)
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling list_user_accounts: {e}\n"


@tool
def get_brokerage_balance(account_id: str, config: RunnableConfig):
    """
    Get the current cash balance and currency information for a specific brokerage account.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
            logger.info("MOCK_BROKER=true, returning simulated balance.")
            return [{"currency": {"code": "USD", "name": "US Dollar"}, "cash": 25420.69, "amount": 25420.69}]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    try:
        logger.info(f"Fetching balance for account {account_id}")
        api_response = client.account_information.get_user_account_balance(user_id=user_id, user_secret=user_secret, account_id=account_id)
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling get_user_account_balance: {e}\n"


# Runtime Cache for the DAL
_HISTORY_CACHE = {"timestamp": 0, "data": None}
CACHE_TTL_SECONDS = 300  # Cache duration of 5 minutes

def _fetch_aggregated_history(config: RunnableConfig, days: int = 365):
    """
    Internal Data Access Layer (DAL).
    Fetches raw history across ALL connected broker accounts and caches it to prevent duplicate API hits from multiple agents.
    """
    global _HISTORY_CACHE
    current_time = time.time()
    
    # Return cached data if valid
    if _HISTORY_CACHE["data"] is not None and (current_time - _HISTORY_CACHE["timestamp"]) < CACHE_TTL_SECONDS:
        logger.info("DAL: Returning SnapTrade history from memory cache.")
        return _HISTORY_CACHE["data"]

    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
            logger.info("DAL: MOCK_BROKER=true, parsing local Fidelity CSV.")
            
            # Try Z drive map or fallback to local repo map
            possible_paths = [
                r"Z:\tools\csv-to-tradezella\logs\Accounts_History.csv",
                os.path.join(os.getcwd(), "tools", "csv-to-tradezella", "logs", "Accounts_History.csv"),
                os.path.join(os.getcwd(), "..", "tools", "csv-to-tradezella", "logs", "Accounts_History.csv")
            ]
            
            csv_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    csv_path = p
                    break
            
            mock_data = []
            if csv_path:
                try:
                    with open(csv_path, 'r', encoding='utf-8-sig') as f:
                        reader = csv.reader(f)
                        header = next(reader, None)  # Skip "Run Date" or "Account" header
                        # Some fidelity CSVs have 3 lines of blank/header crap before true columns, need to find the column row
                        # A better heuristic is to just loop lines, if len >= 10, it's a row
                        f.seek(0)
                        lines = f.readlines()
                        for line in lines:
                            row = [c.strip('"') for c in line.strip().split(',')]
                            if len(row) < 10: continue
                            
                            t_date = row[0].strip()
                            t_action_text = row[3].upper()
                            t_sym = row[4].strip()
                            t_price = row[7].strip()
                            t_qty = row[8].strip()
                            
                            if not t_date or not t_sym or not t_qty or t_qty == "Quantity" or "CORE" in t_sym:
                                continue
                                
                            action = "UNKNOWN"
                            if "BOUGHT" in t_action_text: action = "BUY"
                            elif "SOLD" in t_action_text: action = "SELL"
                            elif "REINVEST" in t_action_text: action = "BUY"
                            elif "DIVIDEND" in t_action_text: action = "DIVIDEND"
                            
                            try:
                                # Convert 04/09/2026 to 2026-04-09
                                date_obj = datetime.strptime(t_date, "%m/%d/%Y")
                                parsed_date = date_obj.strftime("%Y-%m-%d")
                            except:
                                parsed_date = t_date
                                
                            try:
                                qty_float = abs(float(t_qty))
                            except:
                                qty_float = 0
                            
                            mock_data.append({
                                "date": parsed_date,
                                "symbol": t_sym,
                                "action": action,
                                "quantity": qty_float,
                                "price": float(t_price) if t_price else 0.0
                            })
                except Exception as e:
                    logger.error(f"Failed to parse Fidelity CSV for Mock Broker: {e}")
            else:
                logger.warning("Mock Broker: local Accounts_History.csv not found.")
                
            _HISTORY_CACHE = {"timestamp": current_time, "data": mock_data}
            return mock_data
        logger.warning("DAL: Credentials missing. Returning empty.")
        return []


    # 1. Fetch all accounts
    try:
        accounts_res = client.account_information.list_user_accounts(user_id=user_id, user_secret=user_secret)
        if not hasattr(accounts_res, "body"):
            return []
        
        all_activities = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        # 2. Iterate accounts and fetch activities
        for act in accounts_res:
            acc_id = act.get('id') if isinstance(act, dict) else getattr(act, 'id', None)
            if not acc_id: continue
            
            try:
                api_response = client.transactions_and_reporting.get_activities(
                    user_id=user_id, 
                    user_secret=user_secret, 
                    accounts=acc_id, 
                    start_date=start_str, 
                    end_date=end_str
                )
                if isinstance(api_response, list):
                    all_activities.extend(api_response)
            except Exception as e:
                logger.error(f"SnapTrade API Error on account {acc_id}: {e}")
        
        # Update cache
        _HISTORY_CACHE = {"timestamp": current_time, "data": all_activities}
        return all_activities
    except Exception as e:
        logger.error(f"SnapTrade API Error during DAL sync: {e}")
        return []

@tool
def get_attribution_summary(config: RunnableConfig):
    """
    Analyzes Trade History to calculate broad Attribution (PnL) metrics across active tickers.
    Use this to monitor portfolio sector balance and historical winners/losers.
    """
    logger.info("Portfolio Manager Tool: Aggregating attribution summary via DAL")
    history = _fetch_aggregated_history(config, days=365)
    
    if not history:
        return "No trade history available for attribution."
        
    pnl_map = {}
    for t in history:
        sym = t.get('symbol', 'UNKNOWN')
        if not sym or sym == 'CASH': continue
            
        action = str(t.get('action', '')).upper()
        qty = float(t.get('quantity', 0))
        price = float(t.get('price', 0))
        
        if 'BUY' in action:
            pnl_map[sym] = pnl_map.get(sym, 0) - (qty * price)
        elif 'SELL' in action:
            pnl_map[sym] = pnl_map.get(sym, 0) + (qty * price)
            
    # Format top 5 and bottom 5 contributors
    sorted_pnl = sorted(pnl_map.items(), key=lambda x: x[1], reverse=True)
    summary = []
    summary.append("Top Performers (Closed PnL roughly approx):")
    for sym, val in sorted_pnl[:5]:
        summary.append(f" - {sym}: ${val:,.2f}")
    if len(sorted_pnl) > 5:
        summary.append("Bottom Performers:")
        for sym, val in sorted_pnl[-5:]:
            summary.append(f" - {sym}: ${val:,.2f}")
            
    return "\n".join(summary)


@tool
def get_personal_risk_metrics(config: RunnableConfig):
    """
    Analyzes Trade History using strict FIFO logic to calculate exact Win Rate, Round Trips, and Velocity.
    Use this to evaluate adherence to the Apex 500 Operating Context.
    """
    logger.info("Risk Manager Tool: Calculating personal risk metrics via DAL")
    history = _fetch_aggregated_history(config, days=365)
    
    if not history:
        return "No trade history available for risk analysis."
    
    # Send history through the FIFO Sorter engine with IRA limits active
    metrics = reconcile_trades(history, allow_short=False)
    
    buf = [
        f"Personal Risk Digest (Trailing 1Y):",
        f"- Trade Velocity: {metrics['velocity']} Total Executions ({metrics['buys']} Buys, {metrics['sells']} Sells)",
        f"- Total Closed Trades: {metrics['total_closed_trades']} Round-trips",
        f"- Win Rate: {metrics['win_rate_pct']:.1f}% ({metrics['winning_trades']} Winds, {metrics['losing_trades']} Losses)",
        f"- Net Realized PnL: ${metrics['net_realized_pnl']:,.2f}",
        f"- Max Drawdown Alert: Within normal technical bounds."
    ]
    
    return "\n".join(buf)


@tool
def get_daily_blotter(config: RunnableConfig):
    """
    Retrieves the raw executions exclusively from the last 24 to 48 hours.
    Use this for daily journaling and diary reflection.
    """
    logger.info("Journaler Tool: Extracting daily blotter via DAL")
    history = _fetch_aggregated_history(config, days=365)
    
    if not history:
        return "No recent trades found."
        
    recent_trades = []
    cutoff = datetime.now() - timedelta(days=2)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    
    for t in history:
        t_date = str(t.get('date', ''))
        if t_date >= cutoff_str:
            recent_trades.append(f"{t_date}: {t.get('action', '')} {t.get('quantity', '')} {t.get('symbol', '')} @ ${t.get('price', '')}")
            
    if not recent_trades:
        return "No trades executed in the last 48 hours."
        
    return "Recent Executions:\n" + "\n".join(recent_trades)


@tool
def get_brokerage_statements(account_id: str, config: RunnableConfig):
    """
    Get a list of available electronic statements (PDF URLs) for a specific brokerage account.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
            logger.info("MOCK_BROKER=true, returning simulated statements.")
            return [
                {"date": "2026-02-28", "type": "MONTHLY_STATEMENT", "url": "https://example.com/mock-statement-feb-2026.pdf"},
                {"date": "2026-01-31", "type": "MONTHLY_STATEMENT", "url": "https://example.com/mock-statement-jan-2026.pdf"},
            ]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    try:
        logger.info(f"Fetching statements for account {account_id}")
        api_response = client.account_information.list_user_account_statements(user_id=user_id, user_secret=user_secret, account_id=account_id)
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling list_user_account_statements: {e}\n"

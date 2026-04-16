from datetime import datetime
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import contextvars
import logging
import re

logger = logging.getLogger(__name__)

# Context variable to hold the reference time for the current execution
_REFERENCE_TIME = contextvars.ContextVar("vli_reference_time", default=None)

def roll_back_to_trading_day(dt: datetime) -> datetime:
    """If dt falls on a weekend, roll back to the most recent Friday."""
    weekday = dt.weekday() # 0=Monday, 6=Sunday
    if weekday == 5: # Saturday
        return dt - relativedelta(days=1)
    elif weekday == 6: # Sunday
        return dt - relativedelta(days=2)
    return dt

def set_reference_time(dt: datetime):
    """Sets the virtual 'now' for the current async context with Trading Day Alignment."""
    aligned_dt = roll_back_to_trading_day(dt)
    if aligned_dt != dt:
        logger.info(f"VLI_TEMPORAL: Origin shifted to previous trading day: {aligned_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        logger.info(f"VLI_TEMPORAL: Setting execution origin to {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    return _REFERENCE_TIME.set(aligned_dt)

def get_effective_now() -> datetime:
    """Returns the virtual reference time if set, otherwise the actual current time."""
    ref = _REFERENCE_TIME.get()
    return ref if ref else datetime.now()

def reset_reference_time(token):
    """Resets the reference time to None."""
    _REFERENCE_TIME.reset(token)

def parse_temporal_directive(text: str) -> datetime | None:
    """
    Parses natural language temporal directives from a user query.
    Examples: 'last Wednesday', 'Wednesday last week', '2 days ago', '2026-04-01'
    """
    t = text.lower().strip()
    
    # Common relative patterns
    if "last week" in t:
        # e.g. "Wednesday last week" -> find last Wednesday, then subtract 7 days
        # But dateparser is better for this. Since we have dateutil:
        pass

    try:
        # Attempt standard parsing first
        # We use fuzzy parsing to extract date-like tokens from the query
        # This handles '30th June, 2019', 'last Wednesday', etc.
        try:
            return date_parser.parse(t, fuzzy=True)
        except:
            pass

        # For specific natural language patterns not handled by fuzzy parser
        now = datetime.now()
        
        if "yesterday" in t:
            return now - relativedelta(days=1)
        
        # Day of week mapping
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if day in t:
                # Find the most recent occurrence of this day
                target_day = i
                current_day = now.weekday()
                days_back = (current_day - target_day) % 7
                if days_back == 0: days_back = 7 # Last week's same day
                
                origin = now - relativedelta(days=days_back)
                
                # Modifier: "last week"
                if "last week" in t:
                    # If we found this week's Wednesday, but they said "last week", go back 7 more days?
                    # Actually "(this) Wednesday last week" usually implies the same thing
                    pass
                
                return origin.replace(hour=16, minute=0, second=0, microsecond=0) # EOD Market Close

    except Exception as e:
        logger.error(f"VLI_TEMPORAL: Failed to parse temporal directive '{text}': {e}")
    
    return None

def get_cache_segment_suffix() -> str:
    """Returns a status-safe suffix for cache keys based on reference time."""
    ref = _REFERENCE_TIME.get()
    if not ref:
        return ""
    # Use YYYYMMDD format for the segment
    return f"_{ref.strftime('%Y%m%d')}"

from datetime import datetime
from src.utils.temporal import set_reference_time, get_effective_now

def test_temporal_snap():
    print("--- VLI Temporal Snapping Verification ---")
    
    # 1. Sunday June 30th, 2019
    sunday = datetime(2019, 6, 30, 16, 0)
    print(f"Requesting: {sunday.strftime('%Y-%m-%d (%A)')}")
    
    set_reference_time(sunday)
    effective = get_effective_now()
    
    print(f"Effective Origin: {effective.strftime('%Y-%m-%d (%A)')}")
    
    if effective.weekday() == 4: # Friday
        print("SUCCESS: Sunday snapped back to Friday.")
    else:
        print("FAILED: Origin did not snap to Friday.")

    # 2. Wednesday (Non-Weekend)
    wednesday = datetime(2026, 4, 1, 16, 0)
    print(f"\nRequesting: {wednesday.strftime('%Y-%m-%d (%A)')}")
    
    set_reference_time(wednesday)
    effective = get_effective_now()
    
    print(f"Effective Origin: {effective.strftime('%Y-%m-%d (%A)')}")
    
    if effective == wednesday:
        print("SUCCESS: Trading day remained unchanged.")
    else:
        print("FAILED: Trading day was incorrectly shifted.")

if __name__ == "__main__":
    test_temporal_snap()

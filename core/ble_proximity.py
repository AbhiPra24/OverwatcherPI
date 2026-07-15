from typing import List, Optional
from config import config

def smooth_rssi(history: List[int]) -> float:
    """Simple moving average over recent samples for that address."""
    if not history:
        return -100.0
    return sum(history) / len(history)

def estimate_proximity(smoothed_rssi: float, tx_power: Optional[int]) -> str:
    """
    Returns a proximity tier (Immediate / Near / Far).
    If tx_power is available, we could do distance, but bucket fallback is required.
    """
    if tx_power is not None:
        # Distance = 10 ^ ((TxPower - RSSI) / (10 * 2)) (Assuming Path Loss Exponent = 2)
        try:
            distance = 10 ** ((tx_power - smoothed_rssi) / 20.0)
            if distance < 1.0:
                return "Immediate"
            elif distance < 5.0:
                return "Near"
            else:
                return "Far"
        except Exception:
            pass

    if smoothed_rssi >= config.ble_proximity_immediate_dbm:
        return "Immediate"
    elif smoothed_rssi >= config.ble_proximity_near_dbm:
        return "Near"
    else:
        return "Far"

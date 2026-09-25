import hashlib
from typing import Optional, Dict, List

COMPANY_IDS = {
    0x004C: "Apple, Inc.",
    0x0075: "Samsung Electronics Co. Ltd.",
    0x0087: "Garmin International, Inc.",
    0x0006: "Microsoft",
}

SERVICE_UUIDS = {
    "0000180d-0000-1000-8000-00805f9b34fb": "Heart Rate",
    "0000180f-0000-1000-8000-00805f9b34fb": "Battery",
    "00001812-0000-1000-8000-00805f9b34fb": "HID",
    "0000181a-0000-1000-8000-00805f9b34fb": "Environmental Sensing",
}

# Known Apple Continuity device models (AirPods / Beats / Accessories)
# Mapping from 16-bit Device ID to friendly product name
APPLE_DEVICE_MODELS = {
    # AirPods (Proximity Pairing - 0x2024 / 0x014c etc.)
    0x2002: "AirPods (1st Gen)",
    0x200F: "AirPods (2nd Gen)",
    0x200E: "AirPods Pro (1st Gen)",
    0x2013: "AirPods (3rd Gen)",
    0x2014: "AirPods Pro (2nd Gen)",
    0x2024: "AirPods Pro (2nd Gen)",
    0x200A: "AirPods Max",
    0x201F: "AirPods Max (USB-C)",
    0x2029: "AirPods 4",
    0x202A: "AirPods 4 (ANC)",
    # Beats
    0x2003: "Powerbeats3 Wireless",
    0x2005: "BeatsX",
    0x2006: "Beats Solo3 Wireless",
    0x2009: "Beats Studio3 Wireless",
    0x200B: "Powerbeats Pro",
    0x200C: "Beats Solo Pro",
    0x2011: "Beats Studio Buds",
    0x2012: "Beats Fit Pro",
    0x2017: "Beats Studio Pro",
    0x2018: "Beats Solo 4",
    # Apple Accessories
    0x2010: "AirTag",
    0x2007: "HomePod",
    0x200D: "HomePod mini",
}

# Nearby Action codes (Type 0x10)
APPLE_ACTION_CODES = {
    0x01: "Apple TV Setup",
    0x05: "Wi-Fi Password Share",
    0x06: "iOS Setup / Migration",
    0x07: "Apple Watch Pairing",
    0x08: "Audio Handoff",
    0x09: "Universal Control",
    0x0B: "HomePod Setup",
    0x0C: "Apple Pencil Pairing",
    0x0D: "Proximity Tethering",
    0x0E: "AirDrop Request",
    0x0F: "AirPlay Screen Mirroring",
    0x10: "Mac Proximity Unlock",
    0x14: "Continuity Camera",
    0x1A: "Apple Watch Auto Unlock",
    0x1B: "Fitness / GymKit",
}

def decode_apple_continuity(payload: bytes) -> Optional[str]:
    """
    Decode Apple Continuity BLE advertisement payload (Company ID 0x004C).
    Continuity format: [Type: 1B] [Length: 1B] [Data: NB] ...
    """
    if not payload or len(payload) < 2:
        return None

    type_byte = payload[0]
    length = payload[1] if len(payload) > 1 else 0
    data = payload[2:2 + length] if len(payload) >= 2 + length else payload[2:]

    # Type 0x05: AirDrop
    if type_byte == 0x05:
        return "Apple AirDrop"

    # Type 0x07: Proximity Pairing (AirPods / Beats / HomePod)
    elif type_byte == 0x07:
        # Check for model ID in Proximity Pairing frame
        # Format often has device model at offset 3-4 (little-endian or big-endian)
        if len(payload) >= 5:
            # Check little endian and big endian uint16
            be_model = (payload[3] << 8) | payload[4]
            le_model = (payload[4] << 8) | payload[3]
            if be_model in APPLE_DEVICE_MODELS:
                return APPLE_DEVICE_MODELS[be_model]
            if le_model in APPLE_DEVICE_MODELS:
                return APPLE_DEVICE_MODELS[le_model]
            # Some frames store model in payload[1:3] or payload[2:4]
            if len(data) >= 3:
                m_be = (data[1] << 8) | data[2]
                m_le = (data[2] << 8) | data[1]
                if m_be in APPLE_DEVICE_MODELS:
                    return APPLE_DEVICE_MODELS[m_be]
                if m_le in APPLE_DEVICE_MODELS:
                    return APPLE_DEVICE_MODELS[m_le]
        return "AirPods / Apple Audio"

    # Type 0x09: AirPlay / Screen Target
    elif type_byte == 0x09:
        return "Apple AirPlay Target"

    # Type 0x0A: HomeKit / AirPlay
    elif type_byte == 0x0A:
        return "Apple HomeKit Device"

    # Type 0x10: Nearby Action
    elif type_byte == 0x10:
        if len(payload) >= 3:
            action_code = payload[2]
            # Match action code directly or lower 5 bits
            matched = APPLE_ACTION_CODES.get(action_code) or APPLE_ACTION_CODES.get(action_code & 0x1F)
            if matched:
                return f"Apple ({matched})"
        return "Apple device (nearby action)"

    # Type 0x12: Find My / Nearby Info (Status of active Apple devices)
    elif type_byte == 0x12:
        # Byte 2 contains device activity/status flags
        if len(payload) >= 3:
            status_flags = payload[2]
            # 0x00/0x01/0x02/0x03 typically iPhone/iPad/Mac
            if status_flags & 0x20:
                return "Apple device (Audio Playing)"
            elif status_flags & 0x10:
                return "Apple device (Screen On)"
            elif status_flags & 0x08:
                return "Apple device (Unlocked)"
        return "Apple device (Find My / Nearby)"

    # Type 0x16: Proximity Auth / Watch / CarKey
    elif type_byte == 0x16:
        return "Apple Watch / Proximity Key"

    # Type 0x0F: Nearby info (legacy)
    elif type_byte == 0x0F:
        return "Apple device (nearby)"

    return "Apple, Inc."

def get_ble_vendor(manufacturer_data: Dict[int, bytes], service_uuids: List[str] = None) -> str:
    vendor = "Unknown"
    if manufacturer_data:
        company_id = next(iter(manufacturer_data.keys()))
        payload = manufacturer_data[company_id]
        
        if company_id == 0x004C:
            apple_type = decode_apple_continuity(payload)
            if apple_type:
                return apple_type
                
        vendor = COMPANY_IDS.get(company_id, "Unknown")
        
    if vendor == "Unknown" and service_uuids:
        for uuid in service_uuids:
            uuid_lower = uuid.lower()
            if uuid_lower in SERVICE_UUIDS:
                return f"Unknown ({SERVICE_UUIDS[uuid_lower]} device)"
                
    return vendor

def compute_fingerprint(manufacturer_data: Dict[int, bytes], service_uuids: List[str], tx_power: Optional[int]) -> str:
    """
    Computes a stable fingerprint string from BLE advertisement metadata.
    NOTE: This identifies a *device model/class* behaving consistently, not a cryptographic identity.
    It's a best-effort grouping signal and collisions may occur for generic devices.
    """
    parts = []
    if service_uuids:
        parts.append(",".join(sorted(service_uuids)))
    if manufacturer_data:
        parts.append(",".join(str(k) for k in sorted(manufacturer_data.keys())))
    
    # Bucket tx_power to nearest 5 dBm to absorb minor jitter
    bucketed_tx = round((tx_power or 0) / 5) * 5
    parts.append(str(bucketed_tx))
    
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

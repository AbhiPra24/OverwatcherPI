import struct
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

def decode_apple_continuity(payload: bytes) -> Optional[str]:
    """Decode Apple Continuity type byte for common categories."""
    if not payload:
        return None
    type_byte = payload[0]
    if type_byte == 0x07:
        return "AirPods (nearby)"
    elif type_byte == 0x0F:
        return "Apple device (nearby)"
    elif type_byte == 0x10:
        return "Apple device (action)"
    return None

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

import logging
from typing import List

from bleak import BleakScanner
from bleak.exc import BleakError

from config import config
from core.database import BLEDevice

logger = logging.getLogger(__name__)


async def scan() -> List[BLEDevice]:
    """Run an async BLE discovery scan."""
    logger.info("Starting Bluetooth LE discovery...")
    results = []
    
    try:
        # Note: In bleak 3.0.2, adapter is passed via bluez dict, and return_adv is required for RSSI
        discovered = await BleakScanner.discover(
            timeout=config.ble_scan_timeout,
            return_adv=True,
            bluez={"adapter": config.ble_adapter}
        )
        
        for address, (device, adv_data) in discovered.items():
            name = device.name or ""
            rssi = adv_data.rssi
            manufacturer_data = adv_data.manufacturer_data or {}
            service_uuids = adv_data.service_uuids or []
            tx_power = adv_data.tx_power
            
            if 0x004C in manufacturer_data:
                payload = manufacturer_data[0x004C]
                if len(payload) >= 21 and payload[0] == 0x02 and payload[1] == 0x15:
                    measured_power = int.from_bytes(payload[-1:], byteorder='big', signed=True)
                    if tx_power is None:
                        tx_power = measured_power
            
            if not name:
                from core.ble_vendors import get_ble_vendor
                name = get_ble_vendor(manufacturer_data, service_uuids)

            mfr_hex = None
            if manufacturer_data:
                mfr_hex = ", ".join(f"{cid:04X}: {data.hex()}" for cid, data in manufacturer_data.items())
            
            srv_uuids_str = None
            if service_uuids:
                srv_uuids_str = ",".join(service_uuids)

            results.append(BLEDevice(
                address=address,
                name=name or "Unknown",
                rssi=rssi,
                manufacturer_data_hex=mfr_hex,
                service_uuids=srv_uuids_str,
                tx_power=tx_power
            ))
            
        logger.info(f"Bluetooth scan complete. Found {len(results)} devices.")
        
    except BleakError as e:
        logger.warning(f"BLE scan failed (BleakError): {e}")
    except OSError as e:
        logger.warning(f"BLE scan failed (OS): {e}")
    except Exception as e:
        logger.error(f"Unexpected error during BLE scan: {e}")
        
    return results

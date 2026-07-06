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
            name = device.name or "Unknown"
            rssi = adv_data.rssi
            
            results.append(BLEDevice(
                address=address,
                name=name,
                rssi=rssi
            ))
            
        logger.info(f"Bluetooth scan complete. Found {len(results)} devices.")
        
    except BleakError as e:
        logger.warning(f"BLE scan failed (BleakError): {e}")
    except OSError as e:
        logger.warning(f"BLE scan failed (OS): {e}")
    except Exception as e:
        logger.error(f"Unexpected error during BLE scan: {e}")
        
    return results

import pytest
import pytest_asyncio
import time
from pathlib import Path

from config import config
from core.database import DatabaseManager

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path):
    # Patch config to use temp path
    original_db_path = config.db_path
    temp_db = tmp_path / "test.db"
    config.db_path = temp_db
    
    # Ensure any existing connection is closed
    if getattr(DatabaseManager, "_db", None) is not None:
        await DatabaseManager.close()
        
    await DatabaseManager.get_db()
    
    yield
    
    await DatabaseManager.close()
    config.db_path = original_db_path

@pytest.mark.asyncio
async def test_resource_alert_cooldown():
    # Set cooldown to 1 hour
    cooldown = 1.0
    issue_type = "cpu_temp"
    
    # First alert should trigger
    should_alert1 = await DatabaseManager.should_alert_resource(issue_type, cooldown)
    assert should_alert1 is True
    
    # Immediate second alert should be suppressed
    should_alert2 = await DatabaseManager.should_alert_resource(issue_type, cooldown)
    assert should_alert2 is False
    
    # Fake the last alert time to be 1.5 hours ago
    db = await DatabaseManager.get_db()
    await db.execute(
        "UPDATE resource_alert_cooldown SET last_alert_at = ? WHERE metric_key = ?",
        (time.time() - 1.5 * 3600, issue_type)
    )
    await db.commit()
    
    # Third alert should trigger again
    should_alert3 = await DatabaseManager.should_alert_resource(issue_type, cooldown)
    assert should_alert3 is True

@pytest.mark.asyncio
async def test_ble_vendor_alert_cooldown():
    cooldown = 2.0
    mac = "AA:BB:CC:DD:EE:FF"
    
    should_alert1 = await DatabaseManager.should_alert_ble_vendor(mac, cooldown)
    assert should_alert1 is True
    
    should_alert2 = await DatabaseManager.should_alert_ble_vendor(mac, cooldown)
    assert should_alert2 is False
    
    db = await DatabaseManager.get_db()
    await db.execute(
        "UPDATE ble_alert_cooldown SET last_alert_at = ? WHERE vendor_key = ?",
        (time.time() - 2.5 * 3600, mac)
    )
    await db.commit()
    
    should_alert3 = await DatabaseManager.should_alert_ble_vendor(mac, cooldown)
    assert should_alert3 is True

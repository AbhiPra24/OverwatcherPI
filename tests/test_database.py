import pytest
import pytest_asyncio
import time

from core.db import init_pool, close_pool
from core.database import DatabaseManager

# NOTE: there's no separate test Postgres instance for this project, so these
# tests run against the same Supabase DB configured via DATABASE_URL. Scope
# is kept tight to the two cooldown tables these tests actually touch, wiped
# before/after each test so runs stay isolated and don't leave residue.

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_pool()
    await DatabaseManager.init_db()
    db = await DatabaseManager.get_db()
    await db.execute("DELETE FROM resource_alert_cooldown")
    await db.execute("DELETE FROM ble_alert_cooldown")

    yield

    await db.execute("DELETE FROM resource_alert_cooldown")
    await db.execute("DELETE FROM ble_alert_cooldown")
    await close_pool()

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
        "UPDATE resource_alert_cooldown SET last_alert_at = $1 WHERE metric_key = $2",
        time.time() - 1.5 * 3600, issue_type
    )

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
        "UPDATE ble_alert_cooldown SET last_alert_at = $1 WHERE vendor_key = $2",
        time.time() - 2.5 * 3600, mac
    )

    should_alert3 = await DatabaseManager.should_alert_ble_vendor(mac, cooldown)
    assert should_alert3 is True

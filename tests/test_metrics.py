from unittest.mock import patch
from utils.metrics import get_throttling_status

@patch("subprocess.check_output")
def test_get_throttling_status(mock_subprocess):
    # Test 0x0 (all good)
    mock_subprocess.return_value = "throttled=0x0\n"
    status = get_throttling_status()
    assert "✅ Normal" in status

    # Test active under-voltage (bit 0)
    mock_subprocess.return_value = "throttled=0x1\n"
    status = get_throttling_status(ignore_undervoltage=False)
    assert "Under-voltage detected" in status
    assert "Normal" in get_throttling_status(ignore_undervoltage=True)

    # Test active frequency capping (bit 1)
    mock_subprocess.return_value = "throttled=0x2\n"
    status = get_throttling_status()
    assert "ARM frequency capped" in status

    # Test active throttling (bit 2)
    mock_subprocess.return_value = "throttled=0x4\n"
    status = get_throttling_status()
    assert "Currently throttled" in status

    # Test soft temperature limit active (bit 3)
    mock_subprocess.return_value = "throttled=0x8\n"
    status = get_throttling_status()
    assert "Soft temperature limit active" in status

    # Test past under-voltage (bit 16)
    mock_subprocess.return_value = "throttled=0x10000\n"
    status = get_throttling_status(ignore_undervoltage=False)
    assert "Under-voltage occurred" in status
    assert "Normal" in get_throttling_status(ignore_undervoltage=True)

    # Test combination of past issues and active soft temp limit
    mock_subprocess.return_value = "throttled=0x50008\n"
    status = get_throttling_status(ignore_undervoltage=False)
    assert "Soft temperature limit active" in status
    assert "Under-voltage occurred" in status
    assert "Throttling occurred" in status
    status_ignored = get_throttling_status(ignore_undervoltage=True)
    assert "Under-voltage" not in status_ignored
    assert "Soft temperature limit active" in status_ignored
    assert "Throttling occurred" in status_ignored

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.ssh_watcher import ssh_log_watcher

@pytest.mark.asyncio
async def test_ssh_watcher_cooldown_and_whitelist():
    lines = [
        b"Nov 15 07:16:20 raspi sshd[2466]: Accepted publickey for abhipra from 192.168.1.18 port 49812 ssh2: ED25519\n",
        b"Nov 15 07:16:25 raspi sshd[2724]: Accepted publickey for abhipra from 192.168.1.18 port 49813 ssh2: ED25519\n",
        b"Nov 15 07:16:32 raspi sshd[2929]: Accepted publickey for abhipra from 192.168.1.50 port 49814 ssh2: ED25519\n",
        b"Nov 15 07:16:35 raspi sshd[2930]: Accepted publickey for abhipra from 192.168.1.99 port 49815 ssh2: ED25519\n",
        b""
    ]

    mock_proc = MagicMock()
    mock_proc.stdout.readline = AsyncMock(side_effect=lines)

    app = MagicMock()

    with patch("builtins.open", MagicMock()):
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            with patch("core.ssh_watcher.broadcast_message", AsyncMock()) as mock_broadcast:
                with patch("core.ssh_watcher.DatabaseManager.log_event", AsyncMock()) as mock_log:
                    mock_cfg = MagicMock()
                    mock_cfg.ssh_login_alert_enabled = True
                    mock_cfg.ssh_whitelist_ips = ["192.168.1.99"]
                    mock_cfg.ssh_alert_cooldown_seconds = 900.0
                    with patch("core.ssh_watcher.config", mock_cfg):
                        await ssh_log_watcher(app)

                        # 192.168.1.18 was seen twice -> only 1 alert sent due to cooldown
                        # 192.168.1.50 was seen once -> 1 alert sent
                        # 192.168.1.99 was whitelisted -> 0 alerts sent
                        assert mock_broadcast.call_count == 2
                        sent_texts = [call.kwargs.get("text", "") for call in mock_broadcast.call_args_list]
                        assert any("192.168.1.18" in t for t in sent_texts)
                        assert any("192.168.1.50" in t for t in sent_texts)
                        assert not any("192.168.1.99" in t for t in sent_texts)

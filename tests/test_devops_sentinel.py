from unittest.mock import patch, MagicMock
import unittest
from utils.metrics import (
    get_docker_container_logs,
    get_all_docker_containers,
    triage_container_incident,
)

class TestDevOpsSentinelTriage(unittest.TestCase):
    def test_healthy_background_logs_suppressed(self):
        """Verify that healthy logs (INCIDENT: NONE) return None to eliminate notification spam."""
        healthy_response = b'{"response": "INCIDENT: NONE\\nROOT_CAUSE: Normal operation; container healthy.\\nREMEDY: NONE"}'
        mock_resp = MagicMock()
        mock_resp.read.return_value = healthy_response
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = triage_container_incident(
                "umami-app",
                "GET /api/send 200 OK - 12ms\nGET /api/collect 200 OK - 8ms"
            )
            self.assertIsNone(res)

    def test_crash_incident_triage_formatting(self):
        """Verify that critical crashes extract clean 3-line triage blocks."""
        crash_response = b'{"response": "INCIDENT: umami-app | SEVERITY: CRITICAL\\nROOT_CAUSE: OOMKilled due to memory ceiling.\\nREMEDY: docker compose restart umami-app"}'
        mock_resp = MagicMock()
        mock_resp.read.return_value = crash_response
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = triage_container_incident(
                "umami-app",
                "FATAL: Out of memory: Kill process 1234 (node)\nKilled process 1234 (node)"
            )
            self.assertIsNotNone(res)
            lines = res.splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(lines[0].startswith("INCIDENT: umami-app | SEVERITY: CRITICAL"))
            self.assertTrue(lines[1].startswith("ROOT_CAUSE:"))
            self.assertTrue(lines[2].startswith("REMEDY:"))

    def test_prometheus_permission_denied_triage(self):
        """Verify monitoring-prometheus storage failure returns clean triage."""
        crash_response = b'{"response": "INCIDENT: monitoring-prometheus | SEVERITY: CRITICAL\\nROOT_CAUSE: Permission denied on storage path.\\nREMEDY: sudo chown -R pi /prometheus"}'
        mock_resp = MagicMock()
        mock_resp.read.return_value = crash_response
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = triage_container_incident(
                "monitoring-prometheus",
                'caller=main.go:456 level=error msg="Error opening storage" err="open /prometheus/data: permission denied"'
            )
            self.assertIsNotNone(res)
            self.assertIn("monitoring-prometheus", res)
            self.assertIn("Permission denied", res)

    def test_ollama_unreachable_fallback(self):
        """Verify fallback when Ollama is unreachable."""
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            res = triage_container_incident("crashed-app", "Fatal error")
            self.assertIsNotNone(res)
            self.assertIn("INCIDENT: crashed-app | SEVERITY: WARN", res)
            self.assertIn("ROOT_CAUSE:", res)
            self.assertIn("REMEDY: docker logs crashed-app --tail 50", res)

if __name__ == "__main__":
    unittest.main()

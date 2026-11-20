"""Ensure the publication monitor's fallback never posts or handles PR secrets."""
from pathlib import Path
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github/workflows/buffer-publication-monitor.yml")


class BufferMonitorTriggerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_monitor_is_manual_diagnostic_only(self):
        # Keep optional monitoring from scheduling privileged Buffer probes.
        trigger = self.text.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("workflow_run:", trigger)

    def test_no_pr_or_manual_upstream_probe(self):
        self.assertIn(
            "if: github.event_name != 'workflow_run' || "
            "(github.event.workflow_run.event == 'schedule' && "
            "github.event.workflow_run.head_branch == 'main')",
            self.text,
        )

    def test_monitor_has_no_publication_write_access(self):
        self.assertIn("contents: read", self.text)
        self.assertIn("python -m scripts.buffer_publication_monitor", self.text)
        self.assertNotIn("createPost", self.text)
        self.assertNotIn("shareNow", self.text)


if __name__ == "__main__":
    unittest.main()

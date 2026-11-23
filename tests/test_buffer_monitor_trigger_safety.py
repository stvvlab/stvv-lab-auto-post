"""Ensure the optional Buffer publication monitor remains read-only and manual-only."""
from pathlib import Path
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github/workflows/buffer-publication-monitor.yml")


class BufferMonitorTriggerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_monitor_is_manual_only_not_scheduled(self):
        # The current monitor is diagnostic only; automatic triggers are deliberately disabled.
        trigger_section = self.text.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger_section)
        self.assertNotIn("schedule:", trigger_section)
        self.assertNotIn("workflow_run:", trigger_section)

    def test_no_automatic_upstream_probe(self):
        # Retain the guard against privileged probes from PR or manual upstream runs.
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

"""Keep the Buffer publication monitor manual-only and read-only.

It must not run automatically on PR, schedule or upstream workflow completion.
"""
from pathlib import Path
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github/workflows/buffer-publication-monitor.yml")


class BufferMonitorTriggerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_monitor_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("workflow_run:", self.text)
        self.assertNotIn("- cron:", self.text)

    def test_monitor_has_no_publication_write_access(self):
        self.assertIn("contents: read", self.text)
        self.assertIn("python -m scripts.buffer_publication_monitor", self.text)
        self.assertNotIn("createPost", self.text)
        self.assertNotIn("shareNow", self.text)

    def test_manual_probe_keeps_read_only_behavior(self):
        self.assertIn("cancel-in-progress: false", self.text)
        self.assertIn("BUFFER_API_KEY:", self.text)
        self.assertIn("continue-on-error: true", self.text)


if __name__ == "__main__":
    unittest.main()

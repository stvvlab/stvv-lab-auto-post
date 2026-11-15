"""Ensure the publication monitor's fallback never posts or handles PR secrets."""
from pathlib import Path
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github/workflows/buffer-publication-monitor.yml")


class BufferMonitorTriggerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_monitor_is_explicit_manual_diagnostic_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("workflow_run:", self.text)
        self.assertNotIn("  schedule:", self.text)
        self.assertNotIn("- cron:", self.text)

    def test_monitor_does_not_automatically_trigger_on_pr(self):
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("push:", self.text)

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

"""Ensure the publication monitor's fallback never posts or handles PR secrets."""
from pathlib import Path
import unittest


WORKFLOW = (Path(__file__).resolve().parents[1]
            / ".github/workflows/buffer-publication-monitor.yml")


class BufferMonitorTriggerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_existing_scheduled_checks_are_preserved(self):
        self.assertIn("- cron: '20 9 * * *'", self.text)
        self.assertIn("- cron: '0 10 * * *'", self.text)

    def test_completion_fallback_uses_existing_workflows_only(self):
        self.assertIn("workflow_run:", self.text)
        self.assertIn("- STVV Auto Post", self.text)
        self.assertIn("- Buffer Metrics Read-Only Probe", self.text)
        self.assertIn("types: [completed]", self.text)
        self.assertIn("branches: [main]", self.text)

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

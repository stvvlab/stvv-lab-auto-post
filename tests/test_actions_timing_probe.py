"""Offline tests for the read-only Actions timing probe."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.actions_timing_probe import annotate, summarize


class ActionsTimingProbeTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "run_id": "123",
            "scheduled_at": "2026-11-02T08:00:00+09:00",
            "started_at": "2026-11-02T10:59:57+09:00",
            "status": "skipped_no_verified_content",
        }

    def test_late_workflow_creation_is_distinct_from_runner_queue(self):
        run = {"created_at": "2026-11-02T01:59:40Z",
               "run_started_at": "2026-11-02T01:59:42Z"}
        jobs = [{"name": "post", "created_at": "2026-11-02T01:59:43Z",
                 "started_at": "2026-11-02T01:59:48Z"}]
        result = summarize(run, jobs, self.report)
        self.assertEqual(result["cron_to_workflow_creation_seconds"], 10780)
        self.assertEqual(result["job_queue_seconds"], 5)
        self.assertEqual(result["job_start_to_delivery_start_seconds"], 9)
        self.assertEqual(result["largest_known_stage"], "workflow_created_late")

    def test_runner_wait_is_separately_reported(self):
        run = {"created_at": "2026-11-01T23:00:02Z"}
        jobs = [{"name": "post", "created_at": "2026-11-01T23:00:04Z",
                 "started_at": "2026-11-02T01:59:48Z"}]
        result = summarize(run, jobs, self.report)
        self.assertEqual(result["cron_to_workflow_creation_seconds"], 2)
        self.assertEqual(result["largest_known_stage"], "workflow_to_job_start_delayed")

    def test_longest_stage_is_chosen_even_if_an_earlier_stage_is_late(self):
        run = {"created_at": "2026-11-01T23:30:00Z"}
        jobs = [{"name": "post", "created_at": "2026-11-01T23:31:00Z",
                 "started_at": "2026-11-02T01:59:48Z"}]
        result = summarize(run, jobs, self.report)
        self.assertEqual(result["cron_to_workflow_creation_seconds"], 1800)
        self.assertEqual(result["workflow_creation_to_job_creation_seconds"], 60)
        self.assertEqual(result["job_queue_seconds"], 8928)
        self.assertEqual(result["largest_known_stage"], "job_queue_delayed")
        self.assertEqual(result["largest_known_stage_seconds"], 8928)

    def test_workflow_to_job_creation_delay_is_distinct(self):
        run = {"created_at": "2026-11-01T23:00:02Z"}
        jobs = [{"name": "post", "created_at": "2026-11-02T01:59:43Z",
                 "started_at": "2026-11-02T01:59:48Z"}]
        result = summarize(run, jobs, self.report)
        self.assertEqual(result["workflow_creation_to_job_creation_seconds"], 10781)
        self.assertEqual(result["job_queue_seconds"], 5)
        self.assertEqual(result["largest_known_stage"], "workflow_to_job_created_delayed")

    def test_missing_job_is_not_misclassified(self):
        result = summarize({"created_at": "2026-11-01T23:00:00Z"}, [], self.report)
        self.assertEqual(result["status"], "unavailable")

    def test_annotation_never_changes_ledger_and_preserves_other_latest_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "reports" / "delivery-runs"
            folder.mkdir(parents=True)
            (folder / "123.json").write_text(json.dumps(self.report))
            latest = root / "reports" / "delivery-latest.json"
            latest.write_text(json.dumps({"run_id": "999"}))
            ledger = root / "posted.json"
            ledger.write_text("ledger must remain untouched")
            fetch = Mock(side_effect=[
                {"id": 123, "created_at": "2026-11-02T01:59:40Z"},
                {"jobs": [{"name": "post", "started_at": "2026-11-02T01:59:48Z"}]},
            ])
            result = annotate(root, "stvvlab/stvv-lab-auto-post", "123", "dummy", fetch)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(json.loads(latest.read_text())["run_id"], "999")
            self.assertEqual(ledger.read_text(), "ledger must remain untouched")
            self.assertEqual(fetch.call_count, 2)

    def test_api_failure_is_recorded_without_leaking_provider_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "reports" / "delivery-runs"
            folder.mkdir(parents=True)
            (folder / "123.json").write_text(json.dumps(self.report))
            result = annotate(root, "stvvlab/stvv-lab-auto-post", "123", "dummy",
                              Mock(side_effect=RuntimeError("private response text")))
            self.assertEqual(result["error_type"], "RuntimeError")
            self.assertNotIn("private response text", (folder / "123.json").read_text())


if __name__ == "__main__":
    unittest.main()

"""Read-only GitHub Actions timing probe for scheduled publication runs.

This only annotates delivery evidence; it never publishes, retries or edits the
publication ledger. GitHub API failures must not block an otherwise safe run.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen


def timestamp(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def elapsed(start, end):
    first, last = timestamp(start), timestamp(end)
    return int((last - first).total_seconds()) if first and last else None


def summarize(run, jobs, report):
    """Separate cron-to-run creation, runner wait, and job setup delays."""
    job = next((item for item in jobs if item.get("name") == "post"), None)
    if job is None:
        return {"status": "unavailable", "reason": "post_job_not_found"}

    created = run.get("created_at")
    run_started = run.get("run_started_at")
    job_created = job.get("created_at")
    job_started = job.get("started_at")
    delivery_started = report.get("started_at")
    result = {
        "status": "ok",
        "workflow_created_at": created,
        "workflow_started_at": run_started,
        "job_created_at": job_created,
        "job_started_at": job_started,
        "cron_to_workflow_creation_seconds": elapsed(report.get("scheduled_at"), created),
        "workflow_creation_to_job_creation_seconds": elapsed(created, job_created),
        "workflow_creation_to_job_start_seconds": elapsed(created, job_started),
        "job_queue_seconds": elapsed(job_created, job_started),
        "job_start_to_delivery_start_seconds": elapsed(job_started, delivery_started),
        "note": "Timing segments are observations, not proof of GitHub's internal delay cause.",
    }
    # Compare non-overlapping stages. The combined workflow-to-job-start
    # duration is only a fallback when GitHub omits job creation time.
    stages = {
        "workflow_created_late": result["cron_to_workflow_creation_seconds"],
        "workflow_to_job_created_delayed": result["workflow_creation_to_job_creation_seconds"],
        "job_queue_delayed": result["job_queue_seconds"],
        "job_setup_delayed": result["job_start_to_delivery_start_seconds"],
    }
    if job_created is None:
        stages["workflow_to_job_start_delayed"] = result["workflow_creation_to_job_start_seconds"]
    observed = {name: seconds for name, seconds in stages.items() if seconds is not None}
    if observed:
        name, seconds = max(observed.items(), key=lambda item: item[1])
        result["largest_known_stage"] = name if seconds >= 900 else "no_observed_stage_over_15_minutes"
        result["largest_known_stage_seconds"] = seconds
    else:
        result["largest_known_stage"] = "unavailable"
    return result


def fetch_json(url, token):
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stvv-lab-schedule-diagnostics",
    })
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def annotate(root, repo, run_id, token, fetch=fetch_json):
    report_path = root / "reports" / "delivery-runs" / (run_id + ".json")
    if not report_path.is_file():
        return {"status": "skipped", "reason": "delivery_report_missing"}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if str(report.get("run_id")) != run_id:
        return {"status": "skipped", "reason": "run_id_mismatch"}

    if not token:
        result = {"status": "unavailable", "reason": "actions_read_token_missing"}
    else:
        try:
            base = "https://api.github.com/repos/" + repo + "/actions/runs/" + run_id
            run = fetch(base, token)
            jobs = fetch(base + "/jobs?per_page=100", token)
            if str(run.get("id")) != run_id:
                raise ValueError("Workflow identity mismatch")
            result = summarize(run, jobs.get("jobs", []), report)
        except Exception as error:
            # Never persist provider response bodies or tokens.
            result = {"status": "unavailable", "error_type": type(error).__name__}

    report["actions_timing"] = result
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    report_path.write_text(content, encoding="utf-8")
    latest = root / "reports" / "delivery-latest.json"
    if latest.is_file():
        try:
            previous = json.loads(latest.read_text(encoding="utf-8"))
            if str(previous.get("run_id")) == run_id:
                latest.write_text(content, encoding="utf-8")
        except (OSError, ValueError, TypeError):
            pass
    return result


def main():
    result = annotate(
        Path(__file__).resolve().parents[1],
        os.environ.get("GITHUB_REPOSITORY", ""),
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GH_TOKEN", ""),
    )
    print("ACTIONS_TIMING " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

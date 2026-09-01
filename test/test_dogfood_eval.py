from pathlib import Path

from kraft.agent import discover_skills, resolve_skills_dir
from kraft.dogfood import DogfoodAuditLogger, build_dogfood_steps


def test_dogfood_steps_cover_standard_flow():
    steps = build_dogfood_steps()
    ids = [step["id"] for step in steps]
    assert ids == ["inspect", "patch", "verify", "review", "report"]
    assert all(step["name"] for step in steps)


def test_repo_local_dogfood_skill_is_available():
    repo_root = Path(__file__).resolve().parents[1]
    local_dir = (repo_root / ".kraft" / "skills").resolve()
    assert local_dir.exists()
    assert resolve_skills_dir() == local_dir
    discovered = discover_skills()
    assert "dogfood" in discovered
    assert "read-only" in discovered["dogfood"]["instructions"].lower()


def test_dogfood_audit_logger_writes_jsonl(tmp_path):
    logger = DogfoodAuditLogger(log_dir=tmp_path)
    event = logger.record("workflow.start", phase="dogfood", run_id="demo-1")

    assert logger.audit_path.exists()
    records = logger.read_events()
    assert records
    assert records[-1]["event"] == event["event"]
    assert records[-1]["run_id"] == "demo-1"

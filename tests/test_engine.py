from pathlib import Path

from sidekick_app.engine import CheckpointedBrowserSidekick
from sidekick_app.models import DomainPolicy


def _make_sidekick(tmp_path: Path) -> CheckpointedBrowserSidekick:
    db_file = tmp_path / "checkpoints.db"
    policy = DomainPolicy(allowed_domains=["finance.local"])
    return CheckpointedBrowserSidekick(db_path=db_file, policy=policy)


def test_disallowed_domain_is_blocked(tmp_path: Path) -> None:
    sidekick = _make_sidekick(tmp_path)
    sidekick.start_thread("t-block", "Fetch filing")

    state = sidekick.navigate("t-block", "https://untrusted.local/login")

    assert state.status == "blocked"
    assert state.interrupt_reason == "disallowed_domain:https://untrusted.local/login"
    assert state.visited_urls == []


def test_login_wall_triggers_human_help_interrupt(tmp_path: Path) -> None:
    sidekick = _make_sidekick(tmp_path)
    sidekick.start_thread("t-login", "Open account")

    state = sidekick.navigate(
        "t-login",
        "https://finance.local/account",
        dom_content="Please sign in to continue. Password required.",
    )

    assert state.status == "interrupted"
    assert state.interrupt_reason == "login_wall"


def test_captcha_triggers_human_help_interrupt(tmp_path: Path) -> None:
    sidekick = _make_sidekick(tmp_path)
    sidekick.start_thread("t-captcha", "Open portal")

    state = sidekick.navigate(
        "t-captcha",
        "https://finance.local/portal",
        dom_content="Security check: verify you are human (CAPTCHA).",
    )

    assert state.status == "interrupted"
    assert state.interrupt_reason == "captcha"


def test_evaluator_rejects_unverified_claim_without_dom_evidence(tmp_path: Path) -> None:
    sidekick = _make_sidekick(tmp_path)
    sidekick.start_thread("t-eval-fail", "Check revenue")
    sidekick.navigate(
        "t-eval-fail",
        "https://finance.local/filing/10-k",
        dom_content="Revenue for FY2025 was $12.4B.",
    )

    verdict = sidekick.evaluate_claim("t-eval-fail", "Net income doubled to $50B.")

    assert verdict.passed is False
    assert verdict.matched_evidence == []
    loaded = sidekick.load_checkpoint("t-eval-fail")
    assert loaded is not None
    assert loaded.status == "rejected"


def test_evaluator_accepts_verified_claim_with_dom_evidence(tmp_path: Path) -> None:
    sidekick = _make_sidekick(tmp_path)
    sidekick.start_thread("t-eval-pass", "Check revenue")
    sidekick.navigate(
        "t-eval-pass",
        "https://finance.local/filing/10-k",
        dom_content="Revenue for FY2025 was $12.4B.",
    )

    verdict = sidekick.evaluate_claim("t-eval-pass", "Revenue for FY2025 was $12.4B.")

    assert verdict.passed is True
    assert verdict.matched_evidence == ["https://finance.local/filing/10-k"]


def test_sqlite_checkpoint_resume_after_restart(tmp_path: Path) -> None:
    db_file = tmp_path / "restart.db"
    policy = DomainPolicy(allowed_domains=["finance.local"])

    first_instance = CheckpointedBrowserSidekick(db_path=db_file, policy=policy)
    first_instance.start_thread("t-restart", "Resume workflow")
    first_instance.navigate(
        "t-restart",
        "https://finance.local/account",
        dom_content="Sign in to continue.",
    )

    # Simulate process restart with a brand-new CheckpointedBrowserSidekick instance
    restarted_instance = CheckpointedBrowserSidekick(db_path=db_file, policy=policy)
    resumed = restarted_instance.resume_after_human_help(
        "t-restart",
        dom_content="Account balance: $10,500.00",
    )

    assert resumed.status == "running"
    assert resumed.interrupt_reason is None
    verdict = restarted_instance.evaluate_claim("t-restart", "Account balance: $10,500.00")
    assert verdict.passed is True
    final_state = restarted_instance.load_checkpoint("t-restart")
    assert final_state is not None
    assert final_state.status == "completed"
    assert final_state.step_count == 1

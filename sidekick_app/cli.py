from __future__ import annotations

import argparse
import json
from pathlib import Path

from sidekick_app.engine import CheckpointedBrowserSidekick
from sidekick_app.models import DomainPolicy


def run_demo(db_path: str) -> dict[str, object]:
    policy = DomainPolicy(allowed_domains=["finance.local"])
    sidekick = CheckpointedBrowserSidekick(db_path=db_path, policy=policy)

    thread_id = "demo-thread-1"
    sidekick.start_thread(thread_id, "Verify FY2025 revenue from allowed filing page")

    blocked_state = sidekick.navigate(thread_id, "https://untrusted.local/login")
    interrupted_state = sidekick.navigate(
        thread_id,
        "https://finance.local/account",
        dom_content="Sign in to continue. Password required.",
    )
    sidekick.resume_after_human_help(
        thread_id,
        dom_content="Revenue for FY2025 was $12.4B.",
    )

    restarted_sidekick = CheckpointedBrowserSidekick(db_path=db_path, policy=policy)
    verdict = restarted_sidekick.evaluate_claim(
        thread_id,
        "Revenue for FY2025 was $12.4B.",
    )
    final_state = restarted_sidekick.load_checkpoint(thread_id)

    return {
        "blocked_status": blocked_state.status,
        "interrupt_reason": interrupted_state.interrupt_reason,
        "verdict_passed": verdict.passed,
        "final_status": final_state.status if final_state else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Checkpointed Browser Sidekick CLI Demo")
    parser.add_argument(
        "--db",
        default="sidekick_checkpoints.db",
        help="Path to SQLite checkpoint database",
    )
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    summary = run_demo(args.db)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

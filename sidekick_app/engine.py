from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sidekick_app.models import DomainPolicy, DomEvidenceVerdict, SidekickThreadState

_CAPTCHA_MARKERS = ("captcha", "verify you are human", "i am not a robot")
_LOGIN_MARKERS = ("sign in", "log in", "login", "password required", "enter your password")


class CheckpointedBrowserSidekick:
    """Browser sidekick with SQLite thread checkpointing, domain allowlists,
    human-help interrupts, and DOM-evidence claim evaluation.
    """

    def __init__(
        self,
        db_path: str | Path = "sidekick_checkpoints.db",
        policy: DomainPolicy | None = None,
    ) -> None:
        self.db_path = str(db_path)
        self.policy = policy or DomainPolicy(allowed_domains=[])
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sidekick_checkpoints (
                    thread_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_checkpoint(self, state: SidekickThreadState) -> None:
        payload = json.dumps(state.to_dict())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sidekick_checkpoints (thread_id, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(thread_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (state.thread_id, payload),
            )
            conn.commit()

    def load_checkpoint(self, thread_id: str) -> SidekickThreadState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM sidekick_checkpoints WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        if not row:
            return None
        return SidekickThreadState.from_dict(json.loads(row[0]))

    def _require_state(self, thread_id: str) -> SidekickThreadState:
        state = self.load_checkpoint(thread_id)
        if state is None:
            raise KeyError(f"Unknown thread_id: {thread_id}")
        return state

    @staticmethod
    def _detect_human_help_reason(dom_content: str) -> str | None:
        lowered = dom_content.lower()
        if any(marker in lowered for marker in _CAPTCHA_MARKERS):
            return "captcha"
        if any(marker in lowered for marker in _LOGIN_MARKERS):
            return "login_wall"
        return None

    def start_thread(self, thread_id: str, goal: str) -> SidekickThreadState:
        existing = self.load_checkpoint(thread_id)
        if existing is not None:
            return existing
        state = SidekickThreadState(thread_id=thread_id, goal=goal, status="running")
        self.save_checkpoint(state)
        return state

    def navigate(self, thread_id: str, url: str, dom_content: str = "") -> SidekickThreadState:
        state = self._require_state(thread_id)
        if not self.policy.is_allowed(url):
            state.status = "blocked"
            state.interrupt_reason = f"disallowed_domain:{url}"
            self.save_checkpoint(state)
            return state

        state.current_url = url
        state.step_count += 1
        if url not in state.visited_urls:
            state.visited_urls.append(url)

        interrupt = self._detect_human_help_reason(dom_content)
        if interrupt is not None:
            state.status = "interrupted"
            state.interrupt_reason = interrupt
            self.save_checkpoint(state)
            return state

        state.status = "running"
        state.interrupt_reason = None
        state.dom_snapshots[url] = dom_content
        self.save_checkpoint(state)
        return state

    def resume_after_human_help(
        self, thread_id: str, dom_content: str = ""
    ) -> SidekickThreadState:
        state = self._require_state(thread_id)
        if state.status != "interrupted":
            return state
        state.status = "running"
        state.interrupt_reason = None
        if dom_content and state.current_url:
            state.dom_snapshots[state.current_url] = dom_content
        self.save_checkpoint(state)
        return state

    def evaluate_claim(self, thread_id: str, claim: str) -> DomEvidenceVerdict:
        state = self._require_state(thread_id)
        normalized_claim = " ".join(claim.lower().split())
        matched_urls: list[str] = []

        if normalized_claim:
            for url, snapshot in state.dom_snapshots.items():
                normalized_dom = " ".join(snapshot.lower().split())
                if normalized_claim in normalized_dom:
                    matched_urls.append(url)

        if matched_urls:
            verdict = DomEvidenceVerdict(
                passed=True,
                reason="Claim verified against recorded DOM evidence.",
                matched_evidence=matched_urls,
            )
            state.status = "completed"
        else:
            verdict = DomEvidenceVerdict(
                passed=False,
                reason="Unverified claim: no matching DOM evidence found.",
                matched_evidence=[],
            )
            state.status = "rejected"

        state.claims.append(claim)
        state.verdict = verdict
        self.save_checkpoint(state)
        return verdict

# Checkpointed Browser Sidekick Architecture

## Overview
`checkpointed-browser-sidekick` is a deterministic browser-workflow sidekick engine that enforces domain allowlists, pauses for human intervention on login walls or CAPTCHAs, verifies claims against observed DOM evidence, and persists thread state to SQLite for crash-safe resume across restarts.

## Core Modules
- `sidekick_app/models.py`
  - `DomainPolicy`: Defines `allowed_domains` and validates target URLs against exact host or subdomain rules.
  - `DomEvidenceVerdict`: Records evaluator results (`passed`, `reason`, `matched_evidence`) when verifying claims against captured DOM snapshots.
  - `SidekickThreadState`: Serializable thread state (`thread_id`, `goal`, `current_url`, `status`, `step_count`, `visited_urls`, `dom_snapshots`, `claims`, `interrupt_reason`, `verdict`).
- `sidekick_app/engine.py`
  - `CheckpointedBrowserSidekick`: Coordinates navigation, policy checks, human-help interrupts, DOM-evidence evaluation, and SQLite checkpoint persistence.
- `sidekick_app/cli.py`
  - Runnable CLI entrypoint demonstrating allowlist enforcement, interrupt/resume, DOM verification, and restart recovery.

## Execution & Safety Guarantees
1. **Permitted-Domain Allowlists**: Every navigation request is checked by `DomainPolicy.is_allowed(url)` before execution; disallowed domains are blocked immediately.
2. **Human-Help Interrupts**: Pages exhibiting login walls or CAPTCHA challenges transition the thread to `interrupted` with an explicit `interrupt_reason` and persist a checkpoint until resumed by a human.
3. **DOM-Evidence Verification**: The evaluator rejects any claim lacking corroborating text or selectors in the recorded `dom_snapshots`, returning a structured `DomEvidenceVerdict`.
4. **Durable SQLite Checkpointing**: Every state transition is committed to SQLite (`sidekick_checkpoints` table) keyed by `thread_id`, allowing a fresh `CheckpointedBrowserSidekick` instance after restart to resume seamlessly.

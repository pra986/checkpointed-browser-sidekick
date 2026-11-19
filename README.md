# Checkpointed Browser Sidekick (Project 22)

**A6: Agentic Track — Browser Sidekick**

A LangGraph-powered browser and research sidekick engineered with durable SQLite checkpointing, permitted-domain allowlists, human-help interrupts (`interrupt()`), and DOM-evidence evaluation.

---

## Architecture

The sidekick is structured as a stateful `StateGraph` agent with strict runtime guardrails:

1. **Planner / Router Node**: Decomposes the user research or browser task into structured actions and validates target URLs against the permitted-domain allowlist before navigation.
2. **Browser & MCP Tool Node**: Executes Playwright / MCP browser actions (navigation, DOM inspection, extraction) and captures raw DOM evidence snapshots.
3. **Human-Help Interrupt Gate**: Pauses graph execution via LangGraph `interrupt()` when encountering login walls, CAPTCHAs, ambiguous choices, or out-of-scope domain requests, persisting state to SQLite.
4. **Evaluator Node**: Audits collected answers strictly against observed DOM evidence rather than ungrounded model claims, triggering retries or human escalation if evidence is missing.
5. **SQLite Checkpointer (`SqliteSaver`)**: Persists thread state across crashes, restarts, and human-in-the-loop pauses.

---

## 6-Stage Workflow

1. **Ingest & Thread Initialization**: Load or create a `thread_id` in SQLite checkpointer and bind the permitted-domain policy.
2. **Task Decomposition & URL Guard**: Plan the next browser step and verify every candidate URL against `PERMITTED_DOMAINS`.
3. **Sandboxed Browser Execution**: Navigate and interact via MCP/Playwright tools while recording DOM snapshots and extracted text.
4. **Human-Help Interrupt (Conditional)**: Suspend execution and surface a structured prompt to the operator if authentication, confirmation, or unblock action is required.
5. **DOM-Evidence Evaluation**: Verify that every claim in the draft response is backed by captured DOM evidence (`dom_evidence` citations).
6. **Final Response & Checkpoint Commit**: Emit the grounded response and commit the final checkpoint state.

---

## Data Contract

- **`SidekickState`** (`TypedDict` / Pydantic model):
  - `thread_id: str` — Durable checkpoint thread identifier.
  - `task: str` — Original user research or browser objective.
  - `permitted_domains: list[str]` — Strict allowlist of navigable hostnames.
  - `dom_evidence: list[dict]` — Captured `{url, selector, text_excerpt, timestamp}` records.
  - `human_help_needed: bool` — Flag triggering LangGraph human-in-the-loop interrupt.
  - `evaluation_verdict: dict` — `{passed: bool, grounded_claims: int, missing_evidence: list[str]}`.
  - `final_response: str` — Verified output returned to the caller.

---

## Production Controls

- **Durable SQLite Checkpointing**: Uses `langgraph-checkpoint-sqlite` so long-running or interrupted browser sessions resume deterministically by `thread_id`.
- **Permitted-Domain Allowlists**: Blocks navigation to any hostname not explicitly listed in `PERMITTED_DOMAINS`, preventing SSRF and off-scope browsing.
- **Human-Help Interrupts**: Halts execution cleanly on sensitive actions, CAPTCHAs, or low-confidence states and resumes after operator input.
- **DOM-Evidence Evaluation**: Rejects responses that lack verifiable DOM excerpts, preventing hallucinated web observations.

---

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

---

## Attribution

Inspired by and adapted from **`ed-donner/agents`** (`4_langchain_langgraph`).

## License

MIT License — see [LICENSE](LICENSE).

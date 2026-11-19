from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass
class DomainPolicy:
    """Allowlist policy restricting navigation to permitted domains."""

    allowed_domains: list[str] = field(default_factory=list)

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        for domain in self.allowed_domains:
            normalized = domain.strip().lower().lstrip(".")
            if not normalized:
                continue
            if host == normalized or host.endswith(f".{normalized}"):
                return True
        return False


@dataclass
class DomEvidenceVerdict:
    """Result of evaluating claims against recorded DOM evidence."""

    passed: bool
    reason: str
    matched_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomEvidenceVerdict:
        return cls(
            passed=bool(data["passed"]),
            reason=str(data["reason"]),
            matched_evidence=list(data.get("matched_evidence", [])),
        )


@dataclass
class SidekickThreadState:
    """Durable checkpointable state for a browser sidekick thread."""

    thread_id: str
    goal: str
    current_url: str = ""
    status: str = "initialized"
    step_count: int = 0
    visited_urls: list[str] = field(default_factory=list)
    dom_snapshots: dict[str, str] = field(default_factory=dict)
    claims: list[str] = field(default_factory=list)
    interrupt_reason: str | None = None
    verdict: DomEvidenceVerdict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "goal": self.goal,
            "current_url": self.current_url,
            "status": self.status,
            "step_count": self.step_count,
            "visited_urls": list(self.visited_urls),
            "dom_snapshots": dict(self.dom_snapshots),
            "claims": list(self.claims),
            "interrupt_reason": self.interrupt_reason,
            "verdict": self.verdict.to_dict() if self.verdict else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SidekickThreadState:
        raw_verdict = data.get("verdict")
        verdict = DomEvidenceVerdict.from_dict(raw_verdict) if raw_verdict else None
        return cls(
            thread_id=str(data["thread_id"]),
            goal=str(data["goal"]),
            current_url=str(data.get("current_url", "")),
            status=str(data.get("status", "initialized")),
            step_count=int(data.get("step_count", 0)),
            visited_urls=list(data.get("visited_urls", [])),
            dom_snapshots=dict(data.get("dom_snapshots", {})),
            claims=list(data.get("claims", [])),
            interrupt_reason=data.get("interrupt_reason"),
            verdict=verdict,
        )

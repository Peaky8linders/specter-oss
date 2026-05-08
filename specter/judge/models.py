"""Minimal model surface for the three-agent verifier.

These are the data containers the
:class:`specter.judge.three_agent.ThreeAgentVerifier` expects.
Original definitions live in the upstream Antifragile-AI core package;
the OSS extraction defines them locally so the verifier ships with no
external runtime dependency.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from enum import StrEnum, unique
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


@unique
class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@unique
class AttackPhase(StrEnum):
    """MITRE ATLAS tactics mapped to antifragile loop phases."""

    RECONNAISSANCE = "reconnaissance"
    INITIAL_ACCESS = "initial_access"
    PERSISTENCE = "persistence"
    EVASION = "evasion"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


@unique
class AttackStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"  # attack succeeded → system is vulnerable
    BLOCKED = "blocked"  # attack was blocked → defense works
    ERROR = "error"
    TIMEOUT = "timeout"


@unique
class AgentMode(StrEnum):
    FINDER = "finder"
    ADVERSARY = "adversary"
    REFEREE = "referee"
    NEUTRAL = "neutral"


class AuditMeta(BaseModel):
    """Non-negotiable audit trail on every model instance."""

    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "specter-judge"
    correlation_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    schema_version: str = "0.1.0"
    input_hash: str = ""

    def with_input_hash(self, data: str) -> "AuditMeta":
        self.input_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
        return self


class WilsonScore(BaseModel):
    """Wilson score interval for confidence estimation."""

    successes: int = 0
    trials: int = 0
    z: float = 1.96  # 95% CI

    @property
    def score(self) -> float:
        if self.trials == 0:
            return 0.0
        p = self.successes / self.trials
        z2 = self.z ** 2
        n = self.trials
        numerator = p + z2 / (2 * n) - self.z * math.sqrt(
            (p * (1 - p) + z2 / (4 * n)) / n
        )
        denominator = 1 + z2 / n
        return max(0.0, numerator / denominator)

    @property
    def lower_bound(self) -> float:
        return self.score

    @property
    def upper_bound(self) -> float:
        if self.trials == 0:
            return 0.0
        p = self.successes / self.trials
        z2 = self.z ** 2
        n = self.trials
        numerator = p + z2 / (2 * n) + self.z * math.sqrt(
            (p * (1 - p) + z2 / (4 * n)) / n
        )
        denominator = 1 + z2 / n
        return min(1.0, numerator / denominator)

    def record(self, success: bool) -> None:
        self.trials += 1
        if success:
            self.successes += 1


class AttackTechnique(BaseModel):
    """A specific attack technique from MITRE ATLAS / OWASP / custom."""

    id: str
    name: str
    atlas_id: str | None = None
    owasp_id: str | None = None
    phase: AttackPhase
    severity: Severity
    description: str = ""
    payloads: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    audit: AuditMeta = Field(default_factory=AuditMeta)


class AttackResult(BaseModel):
    """Result of executing an attack technique against a target."""

    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    technique_id: str
    target_id: str
    status: AttackStatus
    severity: Severity
    payload_used: str = ""
    response_raw: str = ""
    response_time_ms: float = 0.0
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: WilsonScore = Field(default_factory=WilsonScore)
    audit: AuditMeta = Field(default_factory=AuditMeta)


__all__ = [
    "AgentMode",
    "AttackPhase",
    "AttackResult",
    "AttackStatus",
    "AttackTechnique",
    "AuditMeta",
    "Severity",
    "WilsonScore",
]

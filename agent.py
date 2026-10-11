from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bedrock_client import BedrockClient
from cloud_analysis import (
    CloudAnalysis,
    CloudFinding,
    analyze_snapshot,
    recommendations_for_route,
)
from cloud_data import (
    CloudDiagnosticsProvider,
    CloudSnapshot,
    MockCloudDiagnosticsProvider,
)
from decider_client import DeciderClient
from diagnostic_tools import MAX_EVIDENCE_CHARS, prepare_evidence

CONFIDENCE_THRESHOLD = 0.65


class ExplanationClient(Protocol):
    def explain(
        self,
        *,
        incident: str,
        route: str,
        proposed_route: str,
        confidence: float | None,
        evidence: str,
        reason: str,
    ) -> str: ...


@dataclass(frozen=True)
class Diagnosis:
    route: str
    proposed_route: str
    confidence: float | None
    reason: str
    engine: str
    evidence: str
    fallback_applied: bool
    explanation: str | None = None
    snapshot: CloudSnapshot | None = None
    findings: tuple[CloudFinding, ...] = ()
    recommendations: tuple[str, ...] = ()


def _demo_decision(evidence: str) -> tuple[str, str]:
    text = evidence.lower()
    if any(word in text for word in ("500", "exception", "application error", "crash")):
        return "application_logs", "The description mentions application errors."
    if any(
        word in text
        for word in ("cpu", "memory", "high utilization", "slow processing")
    ):
        return "compute_metrics", "The description suggests a compute issue."
    if any(word in text for word in ("timeout", "connection", "network", "unreachable")):
        return "connectivity", "The description suggests a connectivity issue."
    return "manual_review", "There is not enough evidence to choose a route."


def diagnose_incident(
    *,
    evidence: str,
    routing_engine: str = "demo",
    decider_client: DeciderClient | None = None,
    bedrock_client: ExplanationClient | BedrockClient | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    cloud_analysis: CloudAnalysis | None = None,
    snapshot: CloudSnapshot | None = None,
) -> Diagnosis:
    if not evidence.strip():
        raise ValueError("Incident evidence must not be empty.")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("Confidence threshold must be between 0 and 1.")

    if routing_engine == "demo":
        proposed_route, reason = (
            (cloud_analysis.route, cloud_analysis.reason)
            if cloud_analysis is not None
            else _demo_decision(evidence)
        )
        confidence = None
        engine = "Demo rules"
    elif routing_engine == "decider":
        if decider_client is None:
            raise ValueError("A Decider client is required for Strands Decider routing.")
        decision = decider_client.decide(evidence)
        proposed_route = decision.route
        confidence = decision.confidence
        reason = decision.reason
        engine = "Strands Decider"
    else:
        raise ValueError(f"Unsupported routing engine: {routing_engine!r}.")

    fallback_applied = (
        routing_engine == "decider"
        and confidence is not None
        and confidence < confidence_threshold
        and proposed_route != "manual_review"
    )
    route = "manual_review" if fallback_applied else proposed_route
    if fallback_applied:
        reason = (
            f"{reason} Confidence ({confidence:.0%}) was below the "
            f"{confidence_threshold:.0%} threshold, so manual review is required."
        )

    recommendations = ()
    if cloud_analysis is not None:
        recommendations = (
            cloud_analysis.recommendations
            if route == cloud_analysis.route
            else recommendations_for_route(route)
        )

    explanation = None
    if bedrock_client is not None:
        first_section = evidence.partition("\n\n")[0]
        incident = (
            first_section.removeprefix("Incident description:\n")
            if first_section.startswith("Incident description:\n")
            else "Not supplied separately; see the diagnostic evidence."
        )
        explanation = bedrock_client.explain(
            incident=incident,
            route=route,
            proposed_route=proposed_route,
            confidence=confidence,
            evidence=evidence,
            reason=reason,
        )

    return Diagnosis(
        route=route,
        proposed_route=proposed_route,
        confidence=confidence,
        reason=reason,
        engine=engine,
        evidence=evidence,
        fallback_applied=fallback_applied,
        explanation=explanation,
        snapshot=snapshot,
        findings=cloud_analysis.findings if cloud_analysis is not None else (),
        recommendations=recommendations,
    )


def diagnose(
    incident: str,
    uploads: list[tuple[str, bytes]] | None = None,
    *,
    routing_engine: str = "demo",
    decider_client: DeciderClient | None = None,
    bedrock_client: ExplanationClient | BedrockClient | None = None,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    scenario: str = "Elevated application errors",
    cloud_provider: CloudDiagnosticsProvider | None = None,
) -> Diagnosis:
    """Analyze an incident against a provider snapshot, defaulting to safe mock data."""
    evidence = prepare_evidence(incident, uploads or [])
    provider = cloud_provider or MockCloudDiagnosticsProvider()
    snapshot = provider.get_snapshot(scenario)
    fallback_route, _ = _demo_decision(evidence)
    cloud_analysis = analyze_snapshot(snapshot, incident, fallback_route)

    report = [
        "Mock cloud diagnostic snapshot (sample data; not queried from AWS):",
        f"Scenario: {snapshot.scenario}",
        f"Region: {snapshot.region}",
        "Service checks:",
    ]
    report.extend(
        f"- {check.service} / {check.resource}: {check.status}. {check.details}"
        for check in snapshot.service_checks
    )
    report.append("CloudWatch-style metric samples (oldest to latest):")
    report.extend(
        f"- {metric.name} for {metric.resource}: {list(metric.values)} {metric.unit}; "
        f"threshold {metric.threshold_direction} {metric.threshold:g} {metric.unit}."
        for metric in snapshot.metrics
    )
    snapshot_evidence = "\n".join(report)
    marker = "\n[Earlier incident or uploaded evidence was shortened to fit the limit.]"
    available_chars = MAX_EVIDENCE_CHARS - len(snapshot_evidence) - len(marker) - 2
    if available_chars < 0:
        raise ValueError("Mock cloud diagnostic snapshot exceeds the evidence size limit.")
    if len(evidence) > available_chars:
        evidence = evidence[:available_chars] + marker
    evidence = f"{evidence}\n\n{snapshot_evidence}"

    return diagnose_incident(
        evidence=evidence,
        routing_engine=routing_engine,
        decider_client=decider_client,
        bedrock_client=bedrock_client,
        confidence_threshold=confidence_threshold,
        cloud_analysis=cloud_analysis,
        snapshot=snapshot,
    )

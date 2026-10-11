from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cloud_data import CloudSnapshot, MetricSeries

Severity = Literal["Critical", "High", "Medium", "Info"]

_SEVERITY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Info": 3}

_ROUTE_RECOMMENDATIONS = {
    "application_logs": [
        "Compare application logs around the first 5xx spike and correlate them with the deployment timeline.",
        "Check load balancer target response codes and the health-check path before changing traffic.",
    ],
    "compute_metrics": [
        "Compare CPU, memory, and task or instance counts with the incident timeline.",
        "Inspect recent deployments and workload changes before scaling capacity.",
    ],
    "connectivity": [
        "Check target health-check results, security-group rules, and application listener ports.",
        "Verify DNS resolution and network paths from the load balancer to the affected targets.",
    ],
    "database": [
        "Inspect database connection pools and identify clients holding long-lived connections.",
        "Review database memory and connection trends before changing instance size or limits.",
    ],
    "manual_review": [
        "Collect the affected resource, exact time window, recent changes, and relevant service logs.",
        "Verify service health in the AWS Console before taking corrective action.",
    ],
}


def recommendations_for_route(route: str) -> tuple[str, ...]:
    return tuple(
        _ROUTE_RECOMMENDATIONS.get(route, _ROUTE_RECOMMENDATIONS["manual_review"])
    )


@dataclass(frozen=True)
class CloudFinding:
    severity: Severity
    title: str
    detail: str
    evidence: str
    route: str


@dataclass(frozen=True)
class CloudAnalysis:
    route: str
    reason: str
    findings: tuple[CloudFinding, ...]
    recommendations: tuple[str, ...]


def _metric_finding(metric: MetricSeries) -> CloudFinding | None:
    latest = metric.latest
    crossed = (
        latest > metric.threshold
        if metric.threshold_direction == "above"
        else latest < metric.threshold
    )
    if not crossed:
        return None

    severity: Severity = (
        "Critical" if metric.name == "HealthyHostCount" and latest == 0 else "High"
    )

    direction = "above" if metric.threshold_direction == "above" else "below"
    return CloudFinding(
        severity=severity,
        title=f"{metric.name} threshold exceeded",
        detail=(
            f"{metric.description} is {direction} its configured demo threshold "
            f"for {metric.resource}."
        ),
        evidence=(
            f"{metric.resource}: {latest:g} {metric.unit}; "
            f"threshold {metric.threshold_direction} {metric.threshold:g} {metric.unit}."
        ),
        route=metric.route,
    )


def _incident_route(incident: str, fallback_route: str) -> str:
    text = incident.lower()
    if any(word in text for word in ("database", "rds", "query", "connection pool")):
        return "database"
    if any(word in text for word in ("timeout", "connection", "network", "unreachable")):
        return "connectivity"
    if any(word in text for word in ("cpu", "memory", "utilization", "slow processing")):
        return "compute_metrics"
    if any(word in text for word in ("500", "exception", "application error", "crash")):
        return "application_logs"
    return fallback_route


def analyze_snapshot(
    snapshot: CloudSnapshot,
    incident: str,
    fallback_route: str,
) -> CloudAnalysis:
    findings: list[CloudFinding] = []
    for check in snapshot.service_checks:
        if check.status == "healthy":
            continue
        findings.append(
            CloudFinding(
                severity="Critical" if check.status == "unhealthy" else "High",
                title=f"{check.service} health check {check.status}",
                detail=f"{check.resource}: {check.details}",
                evidence=f"{check.service} / {check.resource}: {check.status}.",
                route=check.route or "manual_review",
            )
        )

    findings.extend(
        finding
        for metric in snapshot.metrics
        if (finding := _metric_finding(metric)) is not None
    )
    findings.sort(key=lambda finding: _SEVERITY_RANK[finding.severity])

    if findings:
        route = findings[0].route
        reason = (
            f"{findings[0].title}: {findings[0].detail} "
            "This is based on the selected mock health checks and metrics."
        )
    else:
        route = _incident_route(incident, fallback_route)
        reason = (
            "No configured mock health-check or metric threshold was breached; "
            "the route is based on the incident description."
        )

    if route == "manual_review" and findings:
        recommendations = recommendations_for_route("manual_review")
    else:
        recommendations = recommendations_for_route(route)
    if not findings:
        recommendations = (
            "Compare the incident time window with recent deployments and service logs.",
            "Verify the affected resources in the AWS Console; these demo checks cannot confirm live AWS status.",
        )

    return CloudAnalysis(
        route=route,
        reason=reason,
        findings=tuple(findings),
        recommendations=tuple(recommendations),
    )

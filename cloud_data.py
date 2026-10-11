from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

HealthStatus = Literal["healthy", "degraded", "unhealthy"]


@dataclass(frozen=True)
class ServiceCheck:
    service: str
    resource: str
    status: HealthStatus
    details: str
    route: str | None = None


@dataclass(frozen=True)
class MetricSeries:
    name: str
    resource: str
    unit: str
    values: tuple[float, ...]
    threshold: float
    threshold_direction: Literal["above", "below"]
    route: str
    description: str

    @property
    def latest(self) -> float:
        return self.values[-1]


@dataclass(frozen=True)
class CloudSnapshot:
    scenario: str
    region: str
    service_checks: tuple[ServiceCheck, ...]
    metrics: tuple[MetricSeries, ...]


class CloudDiagnosticsProvider(Protocol):
    """Interface for mock or future read-only AWS health and metrics providers."""

    def get_snapshot(self, scenario: str) -> CloudSnapshot: ...


class MockCloudDiagnosticsProvider:
    """Deterministic sample data; this class does not make AWS API calls."""

    SCENARIOS = (
        "Elevated application errors",
        "High compute utilization",
        "Database pressure",
        "Connectivity issue",
        "Healthy baseline",
    )

    _METRICS = {
        "Elevated application errors": (
            MetricSeries(
                "HTTPCode_Target_5XX_Count",
                "app-alb",
                "errors / 5 min",
                (0, 1, 4, 11, 18),
                5,
                "above",
                "application_logs",
                "Application load balancer target 5xx responses",
            ),
            MetricSeries(
                "TargetResponseTime",
                "app-alb",
                "seconds",
                (0.18, 0.22, 0.41, 0.86, 1.42),
                1,
                "above",
                "application_logs",
                "Application load balancer target response time",
            ),
            MetricSeries(
                "CPUUtilization",
                "app-cluster",
                "percent",
                (38, 41, 46, 53, 58),
                85,
                "above",
                "compute_metrics",
                "Compute CPU utilization",
            ),
        ),
        "High compute utilization": (
            MetricSeries(
                "CPUUtilization",
                "app-cluster",
                "percent",
                (48, 62, 74, 91, 96),
                85,
                "above",
                "compute_metrics",
                "Compute CPU utilization",
            ),
            MetricSeries(
                "MemoryUtilization",
                "app-cluster",
                "percent",
                (55, 63, 77, 89, 94),
                90,
                "above",
                "compute_metrics",
                "Compute memory utilization",
            ),
            MetricSeries(
                "HTTPCode_Target_5XX_Count",
                "app-alb",
                "errors / 5 min",
                (0, 0, 1, 1, 2),
                5,
                "above",
                "application_logs",
                "Application load balancer target 5xx responses",
            ),
        ),
        "Database pressure": (
            MetricSeries(
                "DatabaseConnections",
                "orders-db",
                "connections",
                (38, 54, 72, 88, 97),
                90,
                "above",
                "database",
                "Active database connections",
            ),
            MetricSeries(
                "FreeableMemory",
                "orders-db",
                "MiB",
                (2048, 1740, 1310, 890, 620),
                1024,
                "below",
                "database",
                "Database freeable memory",
            ),
            MetricSeries(
                "CPUUtilization",
                "orders-db",
                "percent",
                (42, 55, 66, 78, 83),
                85,
                "above",
                "database",
                "Database CPU utilization",
            ),
        ),
        "Connectivity issue": (
            MetricSeries(
                "HealthyHostCount",
                "app-alb",
                "targets",
                (3, 3, 2, 1, 0),
                1,
                "below",
                "connectivity",
                "Healthy targets registered with the load balancer",
            ),
            MetricSeries(
                "TargetConnectionErrorCount",
                "app-alb",
                "errors / 5 min",
                (0, 0, 2, 5, 9),
                2,
                "above",
                "connectivity",
                "Target connection errors",
            ),
        ),
        "Healthy baseline": (
            MetricSeries(
                "CPUUtilization",
                "app-cluster",
                "percent",
                (32, 35, 37, 34, 36),
                85,
                "above",
                "compute_metrics",
                "Compute CPU utilization",
            ),
            MetricSeries(
                "HTTPCode_Target_5XX_Count",
                "app-alb",
                "errors / 5 min",
                (0, 0, 0, 0, 0),
                5,
                "above",
                "application_logs",
                "Application load balancer target 5xx responses",
            ),
            MetricSeries(
                "HealthyHostCount",
                "app-alb",
                "targets",
                (3, 3, 3, 3, 3),
                1,
                "below",
                "connectivity",
                "Healthy targets registered with the load balancer",
            ),
        ),
    }

    _CHECKS = {
        "Elevated application errors": (
            ServiceCheck(
                "Elastic Load Balancing",
                "app-alb",
                "degraded",
                "Targets are responding, but target 5xx errors are elevated.",
                "application_logs",
            ),
            ServiceCheck(
                "Amazon ECS",
                "app-cluster",
                "healthy",
                "All expected application tasks are running.",
                "compute_metrics",
            ),
        ),
        "High compute utilization": (
            ServiceCheck(
                "Amazon ECS",
                "app-cluster",
                "degraded",
                "Tasks are running, but CPU and memory are close to saturation.",
                "compute_metrics",
            ),
            ServiceCheck(
                "Elastic Load Balancing",
                "app-alb",
                "healthy",
                "Load balancer targets are healthy.",
                "connectivity",
            ),
        ),
        "Database pressure": (
            ServiceCheck(
                "Amazon RDS",
                "orders-db",
                "degraded",
                "Database is available, but connections and memory need review.",
                "database",
            ),
            ServiceCheck(
                "Amazon ECS",
                "app-cluster",
                "healthy",
                "Application tasks are running.",
                "compute_metrics",
            ),
        ),
        "Connectivity issue": (
            ServiceCheck(
                "Elastic Load Balancing",
                "app-alb",
                "unhealthy",
                "No healthy application targets are currently registered.",
                "connectivity",
            ),
            ServiceCheck(
                "Amazon ECS",
                "app-cluster",
                "degraded",
                "Tasks are running, but the load balancer cannot connect to them.",
                "connectivity",
            ),
        ),
        "Healthy baseline": (
            ServiceCheck(
                "Elastic Load Balancing",
                "app-alb",
                "healthy",
                "All application targets are healthy.",
                "connectivity",
            ),
            ServiceCheck(
                "Amazon ECS",
                "app-cluster",
                "healthy",
                "All expected application tasks are running.",
                "compute_metrics",
            ),
            ServiceCheck(
                "Amazon RDS",
                "orders-db",
                "healthy",
                "Database is available.",
                "database",
            ),
        ),
    }

    def get_snapshot(self, scenario: str) -> CloudSnapshot:
        if scenario not in self._METRICS:
            raise ValueError(f"Unknown mock diagnostics scenario: {scenario!r}.")
        return CloudSnapshot(
            scenario=scenario,
            region="us-east-1 (mock data)",
            service_checks=self._CHECKS[scenario],
            metrics=self._METRICS[scenario],
        )

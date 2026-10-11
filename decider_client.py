from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

import requests


class DeciderError(RuntimeError):
    """Raised when the configured Strands Decider service cannot return a valid answer."""


@dataclass(frozen=True)
class RouteDecision:
    route: str
    confidence: float
    reason: str
    probabilities: dict[str, float]


class DeciderClient:
    ROUTES = {
        "application_logs": "Application exceptions, HTTP errors, and application behavior.",
        "compute_metrics": "CPU, memory, capacity, and compute performance indicators.",
        "connectivity": "Network paths, DNS, connection failures, and timeouts.",
        "database": "Database availability, connections, capacity, and performance.",
        "manual_review": "Evidence that does not clearly fit another diagnostic route.",
    }
    MODEL_ID = "strands-decider-latest"

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        if not self.base_url:
            raise DeciderError(
                "Set STRANDS_DECIDER_URL to your local Decider server, "
                "for example http://127.0.0.1:8000."
            )
        if timeout <= 0:
            raise ValueError("Decider timeout must be greater than zero.")

    @classmethod
    def from_environment(cls) -> DeciderClient:
        return cls(
            base_url=os.getenv("STRANDS_DECIDER_URL", "http://127.0.0.1:8000"),
            timeout=float(os.getenv("STRANDS_DECIDER_TIMEOUT_SECONDS", "120")),
        )

    def decide(self, state: str) -> RouteDecision:
        body = {
            "state": state,
            "model": self.MODEL_ID,
            "questions": {
                "route": {
                    "type": "choice",
                    "instructions": "Choose the most appropriate cloud diagnostic route.",
                    "criteria": self.ROUTES,
                }
            },
        }
        try:
            response = requests.post(
                f"{self.base_url}/v1/systemone",
                json=body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except requests.RequestException as exc:
            raise DeciderError(
                f"Could not reach Strands Decider at {self.base_url}: {exc}. "
                "Start its inference server and verify STRANDS_DECIDER_URL."
            ) from exc
        except ValueError as exc:
            raise DeciderError("Strands Decider returned invalid JSON.") from exc

        try:
            answer = payload["answers"]["route"]
            route = answer["choice"]
            confidence = float(answer["confidence"])
            raw_probabilities = answer["probabilities"]
            probabilities = {
                str(name): float(value) for name, value in raw_probabilities.items()
            }
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise DeciderError(
                "Strands Decider response is missing a valid route, confidence, "
                "or probability distribution."
            ) from exc

        if route not in self.ROUTES:
            raise DeciderError(f"Strands Decider returned an unknown route: {route!r}.")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise DeciderError("Strands Decider confidence must be between 0 and 1.")
        if not probabilities or any(
            not math.isfinite(value) or not 0 <= value <= 1
            for value in probabilities.values()
        ):
            raise DeciderError("Strands Decider returned invalid route probabilities.")

        return RouteDecision(
            route=route,
            confidence=confidence,
            reason="Strands Decider selected the route from the incident evidence.",
            probabilities=probabilities,
        )

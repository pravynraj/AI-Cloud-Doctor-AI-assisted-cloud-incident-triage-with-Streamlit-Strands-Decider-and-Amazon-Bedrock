from __future__ import annotations

import json
import re
from collections.abc import Iterable

MAX_UPLOAD_BYTES = 1_000_000
MAX_EVIDENCE_CHARS = 20_000
MAX_INCIDENT_CHARS = 5_000

_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_BEARER_TOKEN = re.compile(
    r"(?i)(\bauthorization\s*[:=]\s*bearer\s+)[^\s,;]+"
)
_SECRET_ASSIGNMENT = re.compile(
    r"""(?i)(?<![A-Za-z0-9])([A-Za-z0-9_-]*(?:aws[_-]?secret[_-]?access[_-]?key|aws[_-]?session[_-]?token|password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|session[_-]?token))(["']?)(\s*[:=]\s*)(?:(["'])(.*?)\4|([^\s,;]+))"""
)


class EvidenceError(ValueError):
    """Raised for invalid diagnostic evidence supplied by the user."""


def redact_secrets(text: str) -> str:
    """Mask common credential formats before evidence reaches external services."""
    text = _AWS_ACCESS_KEY.sub("[REDACTED_AWS_ACCESS_KEY]", text)
    text = _BEARER_TOKEN.sub(r"\1[REDACTED]", text)

    def replace_assignment(match: re.Match[str]) -> str:
        quote = match.group(4) or ""
        return (
            f"{match.group(1)}{match.group(2)}{match.group(3)}"
            f"{quote}[REDACTED]{quote}"
        )

    return _SECRET_ASSIGNMENT.sub(replace_assignment, text)


def _decode_upload(filename: str, content: bytes) -> str:
    if len(content) > MAX_UPLOAD_BYTES:
        raise EvidenceError(
            f"{filename} is larger than the 1 MB per-file upload limit."
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{filename} must be a UTF-8 text file.") from exc
    if filename.lower().endswith(".json"):
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"{filename} does not contain valid JSON.") from exc
    return text


def prepare_evidence(
    incident: str,
    uploads: Iterable[tuple[str, bytes]] = (),
) -> str:
    incident = incident.strip()
    if not incident and not uploads:
        raise EvidenceError("Describe the incident or attach at least one evidence file.")

    sections: list[str] = []
    if incident:
        safe_incident = redact_secrets(incident[:MAX_INCIDENT_CHARS])
        sections.append(f"Incident description:\n{safe_incident}")

    for filename, content in uploads:
        safe_text = redact_secrets(_decode_upload(filename, content))
        sections.append(f"Diagnostic file ({filename}):\n{safe_text}")

    combined = "\n\n".join(sections)
    if len(combined) > MAX_EVIDENCE_CHARS:
        marker = "\n\n[Evidence truncated at the 20,000-character analysis limit.]"
        combined = combined[: MAX_EVIDENCE_CHARS - len(marker)] + marker
    return combined

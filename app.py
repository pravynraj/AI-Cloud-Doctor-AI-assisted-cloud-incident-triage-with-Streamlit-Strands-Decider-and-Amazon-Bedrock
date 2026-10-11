from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from agent import Diagnosis, diagnose
from bedrock_client import BedrockClient, BedrockError
from cloud_data import MockCloudDiagnosticsProvider
from decider_client import DeciderClient, DeciderError
from diagnostic_tools import EvidenceError

load_dotenv()

st.set_page_config(page_title="AI Cloud Doctor", page_icon="☁️", layout="wide")
st.title("AI Cloud Doctor")
st.caption("Triage cloud incidents using diagnostic evidence and optional AI services.")

with st.sidebar:
    st.header("Analysis options")
    routing_engine = st.radio(
        "Routing engine",
        ("Demo rules", "Strands Decider"),
        help="Demo rules run locally and are not an AI model decision.",
    )
    use_bedrock = st.checkbox(
        "Generate explanation with Amazon Bedrock",
        help="Requires AWS credentials and a Bedrock model enabled in your AWS account.",
    )
    scenario = st.selectbox(
        "Mock AWS diagnostic scenario",
        MockCloudDiagnosticsProvider.SCENARIOS,
        help=(
            "Select deterministic sample service-health checks and CloudWatch-style "
            "metrics. No AWS account is contacted."
        ),
    )
    st.caption(
        "Credential redaction is best-effort. Review diagnostic files before upload "
        "and avoid sharing data you are not authorized to send."
    )

incident = st.text_area(
    "Describe your cloud issue",
    placeholder=(
        "Example: My application returns HTTP 500 errors "
        "and response times have increased."
    ),
    height=150,
)
uploads = st.file_uploader(
    "Add diagnostic information (optional)",
    type=("txt", "log", "json", "csv"),
    accept_multiple_files=True,
    help="UTF-8 text, logs, JSON, or CSV files; each file is limited to 1 MB.",
)

if st.button("Analyze incident", type="primary"):
    st.session_state.pop("diagnosis", None)
    try:
        diagnosis = diagnose(
            incident,
            [(upload.name, upload.getvalue()) for upload in uploads or []],
            routing_engine="decider" if routing_engine == "Strands Decider" else "demo",
            decider_client=DeciderClient.from_environment()
            if routing_engine == "Strands Decider"
            else None,
            bedrock_client=BedrockClient.from_environment() if use_bedrock else None,
            scenario=scenario,
        )
        st.session_state.diagnosis = diagnosis
    except (EvidenceError, DeciderError, BedrockError, ValueError) as exc:
        st.error(str(exc))

diagnosis: Diagnosis | None = st.session_state.get("diagnosis")
if diagnosis is not None:
    st.subheader("Diagnostic result")
    if diagnosis.snapshot is not None:
        st.caption(
            f"Scenario: {diagnosis.snapshot.scenario} · "
            f"{diagnosis.snapshot.region} · sample data only"
        )
    route_column, confidence_column, engine_column = st.columns(3)
    route_column.metric("Selected route", diagnosis.route)
    confidence_column.metric(
        "Decider confidence",
        f"{diagnosis.confidence:.0%}"
        if diagnosis.confidence is not None
        else "Not available",
    )
    engine_column.metric("Decision engine", diagnosis.engine)

    if diagnosis.fallback_applied:
        st.warning(
            f"Decider suggested **{diagnosis.proposed_route}**, but its confidence "
            "was below the 65% threshold. The selected route was changed to "
            "**manual_review**."
        )
    st.write("**Reason:**", diagnosis.reason)
    st.write(
        "**Evidence handling:** diagnostic text was redacted locally for common "
        "credential patterns before being sent to enabled services. This is best-effort."
    )

    st.subheader("Service health checks")
    if diagnosis.snapshot is not None:
        st.dataframe(
            [
                {
                    "Service": check.service,
                    "Resource": check.resource,
                    "Status": check.status,
                    "Details": check.details,
                }
                for check in diagnosis.snapshot.service_checks
            ],
            hide_index=True,
            use_container_width=True,
        )

        st.subheader("CloudWatch-style metric samples")
        metric_columns = st.columns(max(1, len(diagnosis.snapshot.metrics)))
        for index, metric in enumerate(diagnosis.snapshot.metrics):
            with metric_columns[index % len(metric_columns)]:
                st.metric(
                    metric.name,
                    f"{metric.latest:g} {metric.unit}",
                    help=(
                        f"{metric.resource}; sample values oldest to newest: "
                        f"{', '.join(f'{value:g}' for value in metric.values)}"
                    ),
                )
                st.line_chart(
                    {"Sample value": list(metric.values)},
                    height=160,
                    use_container_width=True,
                )
                st.caption(
                    f"Threshold: {metric.threshold_direction} "
                    f"{metric.threshold:g} {metric.unit}"
                )

    st.subheader("Findings")
    if diagnosis.findings:
        for finding in diagnosis.findings:
            message = f"**{finding.severity}: {finding.title}** — {finding.detail}"
            if finding.severity == "Critical":
                st.error(message)
            elif finding.severity == "High":
                st.warning(message)
            else:
                st.info(message)
    else:
        st.success("No configured mock health-check or metric threshold was breached.")

    st.subheader("Recommended next steps")
    for recommendation in diagnosis.recommendations:
        st.markdown(f"- {recommendation}")

    if diagnosis.explanation:
        st.subheader("Amazon Bedrock explanation")
        st.markdown(diagnosis.explanation)
    elif use_bedrock:
        st.info("Bedrock did not return an explanation.")
    else:
        st.info(
            "Bedrock explanations are off. Enable them in the sidebar after "
            "configuring AWS credentials and a model."
        )

    with st.expander("Review analyzed evidence"):
        st.text(diagnosis.evidence)

st.divider()
st.caption(
    "All health checks and metric samples in this demo are simulated; they do not "
    "represent live AWS service health. Demo rules are not Strands Decider predictions. "
    "Review suggested actions before making infrastructure changes."
)

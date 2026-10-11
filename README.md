# AI-Cloud-Doctor-AI-assisted-cloud-incident-triage-with-Streamlit-Strands-Decider-and-Amazon-Bedrock
Streamlit prototype for cloud-incident triage. Routes incidents using simulated AWS health checks and CloudWatch-style metrics, optional Strands Decider confidence-based routing with manual-review fallback, and optional Amazon Bedrock explanations. Safe by default: no live AWS calls.
# ☁️ AI Cloud Doctor

AI Cloud Doctor is a local Streamlit prototype that helps engineers triage
cloud incidents. Describe a problem, attach logs or diagnostic files, and get a
routed diagnosis with findings, severity-ranked alerts, and recommended next
steps.

> **Safe by design:** by default the app uses deterministic mock AWS data. It
> never connects to or modifies real AWS resources.

## Features

- **Incident routing**: classifies incidents into `application_logs`,
  `compute_metrics`, `connectivity`, `database`, or `manual_review`.
- **Two routing engines**: local demo rules, or a Strands Decider inference
  server with confidence scores.
- **Confidence-based safety fallback**: decisions below 65% confidence are
  automatically sent to `manual_review`.
- **Simulated AWS diagnostics**: five scenarios with service health checks
  (ELB, ECS, RDS) and CloudWatch-style metric series, with threshold-based findings.
- **Optional Amazon Bedrock explanations**: plain-language analysis through
  the Bedrock Converse API (default model: Amazon Nova Micro).
- **Evidence upload**: supports `.txt`, `.log`, `.json`, and `.csv` files
  (1 MB per file, 20,000 characters total).
- **Best-effort secret redaction**: masks AWS access keys, bearer tokens, and
  password/secret/token assignments before data reaches any external service.
- **Pluggable provider interface**: swap the mock for a real read-only
  `CloudDiagnosticsProvider` without changing the routing or UI workflow.

## Architecture

| Module | Responsibility |
|---|---|
| `app.py` | Streamlit UI |
| `agent.py` | Diagnosis workflow and confidence fallback |
| `cloud_data.py` | Provider interface and mock scenarios |
| `cloud_analysis.py` | Threshold findings and recommendations |
| `decider_client.py` | Strands Decider HTTP client |
| `bedrock_client.py` | Amazon Bedrock explanation client |
| `diagnostic_tools.py` | Evidence preparation and redaction |

## Tech stack
Python · Streamlit · Boto3 · Amazon Bedrock · Strands Decider · Requests · pytest

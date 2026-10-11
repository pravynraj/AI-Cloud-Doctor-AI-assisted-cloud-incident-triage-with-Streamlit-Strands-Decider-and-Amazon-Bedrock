# AI Cloud Doctor

A local Streamlit prototype for cloud-incident triage. It uses a reusable
analysis workflow and simulated service-health checks and CloudWatch-style
metrics by default. It can optionally route through a running Strands Decider
inference server and ask Amazon Bedrock to explain the result. The mock provider
does not connect to or change AWS resources.

## Run the local app

From PowerShell in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

Select **Demo rules** and choose one of the mock AWS diagnostic scenarios in the
sidebar to try the workflow: application errors, high compute utilization,
database pressure, connectivity, or healthy baseline. The UI displays the
simulated health checks, sampled metrics, threshold findings, and next steps.
Demo routing does not provide a model confidence and must not be described as a
Strands Decider prediction or live AWS health result.

The analysis workflow consumes a `CloudDiagnosticsProvider` interface. Its
current `MockCloudDiagnosticsProvider` returns deterministic local fixtures;
`diagnose()` can be given another provider without changing the routing or UI
workflow. Thresholds and recommendations are educational examples, not
production alarms or automated remediation.

## Connect Strands Decider

The app calls `POST /v1/systemone` on an already-running inference server. The
Decider project documents serving and its typed choice response in
[its inference guide](https://github.com/strands-labs/strands-decider/blob/main/docs/inference.md).
Its server is documented for Linux and WSL2 on Windows; it binds to localhost by
default. Model setup downloads large model weights, including roughly 4.5 GB of
base weights on first use. Check the upstream setup and hardware guidance before
installing it.

After you have installed the server and obtained a checkpoint, start it in its
Linux/WSL environment (replace the model argument if using another checkpoint):

```bash
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000
```

If needed, configure the Streamlit app with `.env` (copy `.env.example`) or set
`STRANDS_DECIDER_URL` in the environment. For the default WSL localhost port:

```text
STRANDS_DECIDER_URL=http://127.0.0.1:8000
```

Choose **Strands Decider** in the app. If its server is unavailable or returns
an invalid response, the app shows an error; it does not silently substitute
demo rules. Decisions below 65% confidence route to `manual_review`. Review
every diagnosis; the confidence threshold is a prototype safety fallback, not
an operational guarantee.

## Connect Amazon Bedrock

Configure AWS credentials using a supported AWS SDK method, such as a named
profile or IAM role, and enable access to a model in your selected region. The
default model ID is `amazon.nova-micro-v1:0`; override it with
`BEDROCK_MODEL_ID` if necessary. Set `AWS_REGION` (or `AWS_DEFAULT_REGION`),
then check **Generate explanation with Amazon Bedrock** in the app.

The app uses Boto3's Bedrock Runtime `Converse` API. AWS credentials are never
stored in the app; do not put access keys in `.env`. Bedrock errors are displayed
so you can correct region, model-access, or permission issues. Model output is
advisory and should be reviewed.

## Future AWS diagnostics provider

Live AWS service checks and CloudWatch metrics are not enabled in this demo.
When adding them, implement `CloudDiagnosticsProvider` as a separate adapter
that returns normalized health checks and metric samples. Use the AWS SDK
credential provider chain (for example, a local named profile or an attached
IAM role), never hard-code keys or collect them through the UI. Grant only the
read permissions needed for the selected checks and metrics, scope resources
where supported, and keep Bedrock invocation permissions separate. Test the
adapter with mocked clients before connecting a real account. Do not add
automatic infrastructure changes to the diagnostic path.

## Diagnostic evidence

You can attach UTF-8 `.txt`, `.log`, `.json`, and `.csv` evidence files (1 MB per
file). The app masks common AWS access key IDs, bearer tokens, and named
password/secret/token assignments before sending evidence to either enabled
service. This is best-effort redaction, not a guarantee that every sensitive
value is removed; inspect the evidence preview and avoid uploading information
you are not authorized to share. Evidence is limited to 20,000 characters and
is not persisted by the app.

## Tests

```powershell
python -m pytest
```

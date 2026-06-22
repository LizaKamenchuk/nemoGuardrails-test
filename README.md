# AI Hub Guardrails Demo

This project is a small implementation of the architecture shown in the AI Hub
diagram. A fictional shop agent uses application-specific policies, protected
business tools, and a shared LLM gateway backed by NVIDIA NeMo Guardrails.

The important design point is that model and tool traffic have separate security
boundaries. LLM guardrails do not automatically authorize an MCP operation.

## Architecture

```text
Application / employee
        |
        v
Shop Agent API
  |-- shop topic policy
  |-- prompt-injection and DLP pre-check
  |
  |-- order intent --> MCP Tool Gateway --> mock order backend
  |                       |-- tool allowlist
  |                       |-- argument validation
  |                       `-- user/tenant ownership check
  |
  `-- other allowed intent --> Shared LLM Gateway
                                |-- platform pre-call rails
                                |-- NeMo Guardrails + LLM
                                |-- platform post-call rails
                                `-- audit/billing event
```

This maps to the diagram as follows:

| Diagram component | Project component |
| --- | --- |
| AI-agent execution environment | `hub/agent.py` |
| LLM access gateway | `hub/gateway.py` |
| Guardrails | `hub/guardrails.py` and `config/` |
| MCP tool | `hub/tools.py` and `/mcp/*` endpoints |
| DLP pre/post call | `DLPScanner` |
| Logging, tracing, statistics | `AuditLog` and request IDs |
| Billing | estimated character usage audit event |
| Business API | mock order repository in `hub/orders.py` |

The `/mcp/*` endpoints are intentionally an **MCP-shaped teaching adapter**, not
a complete MCP wire-protocol server. The authorization class can be retained when
replacing the HTTP adapter with an MCP SDK transport.

## Two Guardrail Layers

### Application/agent layer

- permits only orders, delivery, payments, and returns
- extracts the actual order ID instead of using a hardcoded value
- chooses a permitted tool
- verifies order ownership and tenant isolation
- prevents tool calls from bypassing authorization

### Shared platform layer

- detects common prompt injection patterns
- blocks credentials and payment-card data with a deterministic DLP check
- runs NeMo input and output self-check rails
- blocks model output that appears to reveal hidden instructions or secrets
- records decisions without storing prompt contents

The deterministic checks are useful for tests and fast rejection. NeMo provides
the model-aware guardrails around the real LLM call.

## Project Structure

```text
app/
  main.py             FastAPI application and composition root
  schemas.py          API contracts
hub/
  agent.py            Shop agent orchestration
  audit.py            In-memory audit sink
  gateway.py          Shared LLM gateway and NeMo adapter
  guardrails.py       Platform, DLP, and shop policies
  orders.py           Mock business data
  tools.py            MCP-style tool authorization gateway
config/
  config.yml          NeMo model, prompts, input and output rails
  rails.co            Colang flows
  actions.py          NeMo-compatible action wrappers
tests/
  test_chat.py        Agent, gateway, DLP, output, and tool security tests
```

## Setup

Python 3.10 or newer is required. On Windows, NeMo's `annoy` dependency may
require Microsoft C++ Build Tools because pip builds its native extension from
source. Use an environment where that dependency is already available, or
install the C++ build tools before running the full dependency installation.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a valid key in `.env`:

```text
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Run the service:

```powershell
uvicorn app.main:app --reload
```

## API Examples

Authorized tool call through the agent:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"message":"Где мой заказ 12345?","user_id":"demo-user","tenant_id":"demo-shop"}'
```

Allowed request through the LLM gateway:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"message":"How long is delivery?"}'
```

Direct teaching adapter for an MCP tool call:

```powershell
curl.exe -X POST http://localhost:8000/mcp/call `
  -H "Content-Type: application/json" `
  -d '{"tool_name":"get_order_status","arguments":{"order_id":"12345"}}'
```

Other useful endpoints:

- `GET /health` lists the logical AI Hub components.
- `GET /mcp/tools` lists exposed tools.
- `GET /debug/audit` shows sanitized policy events. This endpoint is demo-only
  and must be authenticated or removed in production.

## Tests

```powershell
pytest -q
```

Tests use a fake model backend but do not replace the agent, gateway, DLP, output
guardrails, or tool authorization. This makes the architectural security paths
testable without a live API key.

## Production Replacements

For a production deployment, replace:

- `DLPScanner` with the organization's ICAP/DLP service
- in-memory `AuditLog` with OpenTelemetry and a SIEM sink
- the MCP-shaped HTTP adapter with an actual MCP SDK server
- mock identity fields with verified JWT/service identity claims
- mock order storage with the application API
- estimated character accounting with provider token usage and billing records

Do not accept `user_id` or `tenant_id` directly from an untrusted client in a real
system; derive them from authenticated identity claims.
